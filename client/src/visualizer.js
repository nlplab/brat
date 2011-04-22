var Visualizer = (function($, window, undefined) {
    var Visualizer = function(dispatcher, svgContainer) {
      var that = this;

      // OPTIONS

      var margin = { x: 2, y: 1 };
      var boxTextMargin = { x: 0, y: 0 };
      var space = 4;
      var boxSpacing = 1;
      var curlyHeight = 4;
      var arcSpacing = 9; //10;
      var arcSlant = 15; //10;
      var arcStartHeight = 19; //23; //25;
      var arcHorizontalSpacing = 25;
      var rowSpacing = -5;          // for some funny reason approx. -10 gives "tight" packing.
      var dashArray = '3,3';
      var sentNumMargin = 20;
      var smoothArcCurves = true;   // whether to use curves (vs lines) in arcs
      var smoothArcSteepness = 0.5; // steepness of smooth curves (control point)
      var reverseArcControlx = 5;   // control point distance for "UFO catchers"
      var shadowSize = 5;
      var shadowStroke = 5;
      var editedSpanSize = 7;
      var editedArcSize = 3;
      var editedStroke = 7;
      var rowPadding = 2;

      // END OPTIONS


      var svg;
      var svgElement;
      var data = null;
      var dir, doc, args;
      var abbrevs;
      var isRenderRequested;
      var curlyY;

      var infoPrioLevels = ['Unconfirmed', 'Incomplete', 'Warning', 'Error'];

      this.arcDragOrigin = null; // TODO

      // due to silly Chrome bug, I have to make it pay attention
      var forceRedraw = function() {
        if (!$.browser.chrome) return; // not needed
        svgElement.css('margin-bottom', 1);
        setTimeout(function() { svgElement.css('margin-bottom', 0); }, 0);
      }

      var Span = function(id, type, from, to, generalType) {
        this.id = id;
        this.type = type;
        this.from = parseInt(from);
        this.to = parseInt(to);
        this.outgoing = [];
        this.incoming = [];
        this.totalDist = 0;
        this.numArcs = 0;
        this.generalType = generalType;
      };

      var EventDesc = function(id, triggerId, roles, equiv) {
        this.id = id;
        this.triggerId = triggerId;
        var roleList = this.roles = [];
        $.each(roles, function(roleNo, role) {
          roleList.push({ type: role[0], targetId: role[1] });
        });
        if (equiv) this.equiv = true;
      };

      var Row = function() {
        this.group = svg.group();
        this.background = svg.group(this.group);
        this.chunks = [];
        this.hasAnnotations = 0;
      };

      var rowBBox = function(span) {
        var box = span.rect.getBBox();
        var chunkTranslation = span.chunk.translation;
        box.x += chunkTranslation.x;
        box.y += chunkTranslation.y;
        return box;
      };

      var infoPriority = function(infoClass) {
        if (infoClass === undefined) return -1;
        var len = infoPrioLevels.length;
        for (var i = 0; i < len; i++) {
          if (infoClass.indexOf(infoPrioLevels[i]) != -1) return i;
        }
        return 0;
      };

      var clearSVG = function() {
        svg.clear();
        svgContainer.hide();
      };

      var setData = function(_data) {
        data = _data;

        // collect annotation data
        data.spans = {};
        $.each(data.entities, function(entityNo, entity) {
          var span =
              new Span(entity[0], entity[1], entity[2], entity[3], 'entity');
          data.spans[entity[0]] = span;
        });
        var triggerHash = {};
        $.each(data.triggers, function(triggerNo, trigger) {
          triggerHash[trigger[0]] =
              new Span(trigger[0], trigger[1], trigger[2], trigger[3], 'trigger');
        });
        data.eventDescs = {};
        $.each(data.events, function(eventNo, eventRow) {
          var eventDesc = data.eventDescs[eventRow[0]] =
              new EventDesc(eventRow[0], eventRow[1], eventRow[2]);
          var span = $.extend({}, triggerHash[eventDesc.triggerId]); // clone
          span.incoming = []; // protect from shallow copy
          span.outgoing = [];
          span.id = eventDesc.id;
          data.spans[eventDesc.id] = span;
        });
        $.each(data.modifications, function(modNo, mod) {
          if (!data.spans[mod[2]]) {
            dispatcher.post('messages', [[['<strong>ERROR</strong><br/>Event ' + mod[2] + ' (referenced from modification ' + mod[0] + ') does not occur in document ' + data.document + '<br/>(please correct the source data)', 'error', 5]]]);
            throw "BadDocumentError";
          }
          data.spans[mod[2]][mod[1]] = true;
        });
        $.each(data.equivs, function(equivNo, equiv) {
          equiv[0] = "*" + equivNo;
          var equivSpans = equiv.slice(2);
          equivSpans.sort(function(a, b) {
            var aSpan = data.spans[a];
            var bSpan = data.spans[b];
            var tmp = aSpan.from + aSpan.to - bSpan.from - bSpan.to;
            if (tmp) {
              return tmp < 0 ? -1 : 1;
            }
            return 0;
          });
          var len = equivSpans.length;
          for (var i = 1; i < len; i++) {
            var eventDesc = data.eventDescs[equiv[0] + '*' + i] =
                new EventDesc(equivSpans[i - 1], equivSpans[i - 1], [[equiv[1], equivSpans[i]]], true);
            eventDesc.leftSpans = equivSpans.slice(0, i);
            eventDesc.rightSpans = equivSpans.slice(i);
          }
        });
        data.sentInfo = {};

        $.each(data.infos, function(infoNo, info) {
          // TODO error handling
          if (info[0] instanceof Array && info[0][0] == 'sent') { // [['sent', 7], 'Type', 'Text']
            var sent = info[0][1];
            var text = info[2];
            if (data.sentInfo[sent]) {
              text = data.sentInfo[sent].text + '<br/>' + text;
            }
            data.sentInfo[sent] = { type: info[1], text: text };
          } else if (info[0] in data.spans) {
            var span = data.spans[info[0]];
            if (!span.info) {
              span.info = { type: info[1], text: info[2] };
            } else {
              span.info.type = info[1];
              span.info.text += "<br/>" + info[2];
            }
            // prioritize type setting when multiple infos are present
            if (infoPriority(info[1]) > infoPriority(span.shadowClass)) {
              span.shadowClass = info[1];
            }
          }
        });

        // find chunk breaks
        var breaks = [[-1, false]];
        var pos = -1;
        while ((pos = data.text.indexOf('\n', pos + 1)) != -1) {
          breaks.push([pos, true, true]);
        }
        pos = -1;
        while ((pos = data.text.indexOf(' ', pos + 1)) != -1) {
          var wordBreak = true;
          // possible word break: see if it belongs to any spans
          $.each(data.spans, function(spanNo, span) {
            if (span.from <= pos + data.offset && pos + data.offset < span.to) {
              // it does; no word break
              wordBreak = false;
              return false;
            }
          });
          if (wordBreak) breaks.push([pos, false]);
        }
        breaks.sort(function(a, b) { return a[0] - b[0] });

        // split text into chunks
        // format: data.chunks[chunk] = [text, from, to, lineBreak, [spans]]
        data.chunks = [];
        var numBreaks = breaks.length;
        breaks.push([data.text.length, false]);
        var chunkNo = 0;
        for (var breakNo = 0; breakNo < numBreaks; breakNo++) {
          var from = breaks[breakNo][0] + 1;
          var to = breaks[breakNo + 1][0];
          if (from != to) {
            data.chunks.push({
                text: data.text.substring(from, to),
                from: from + data.offset,
                to: to + data.offset,
                lineBreak: breaks[breakNo][1],
                index: chunkNo++,
                spans: [],
                newSentence: breaks[breakNo][2],
              });
          }
        }

        // assign spans to appropriate chunks
        // and copy spans to sortedSpans array
        var sortedSpans = [];
        var numChunks = data.chunks.length;
        for (spanId in data.spans) {
          var span = data.spans[spanId];
          sortedSpans.push(span);
          for (var j = 0; j < numChunks; j++) {
            var chunk = data.chunks[j];
            if (span.to <= chunk.to) {
              chunk.spans.push(span);
              span.chunk = chunk;
              break; // chunks
            }
          }
        }
       
        // assign arcs to spans; calculate arc distances
        data.arcs = [];
        $.each(data.eventDescs, function(eventNo, eventDesc) {
          var dist = 0;
          var origin = data.spans[eventDesc.id];
          if (!origin.chunk) {
            // TODO: include missing trigger ID in error message
            dispatcher.post('messages', [[['<strong>ERROR</strong><br/>Trigger for event "' + eventDesc.id + '" not found in ' + data.document + '<br/>(please correct the source data)', 'error', 5]]]);
            throw "BadDocumentError";
          }
          var here = origin.chunk.index;
          $.each(eventDesc.roles, function(roleNo, role) {
            var target = data.spans[role.targetId];
            if (!target) {
              dispatcher.post('messages', [[['<strong>ERROR</strong><br/>"' + role.targetId + '" (referenced from "' + eventDesc.id + '") not found in ' + data.document + '<br/>(please correct the source data)', 'error', 5]]]);
              throw "BadDocumentError";
            }
            var there = target.chunk.index;
            var dist = Math.abs(here - there);
            var arc = {
              origin: eventDesc.id,
              target: role.targetId,
              dist: dist,
              type: role.type,
              jumpHeight: 0,
            };
            if (eventDesc.equiv) {
              arc.equiv = true;
              eventDesc.equivArc = arc;
              arc.eventDescId = eventNo;
            }
            origin.totalDist += dist;
            origin.numArcs++;
            target.totalDist += dist;
            target.numArcs++;
            data.arcs.push(arc);
            target.incoming.push(arc);
            origin.outgoing.push(arc);
          }); // roles
        }); // eventDescs

        // last edited highlighting
        if (args.edited) {
          $.each(args.edited, function(editedNo, edited) {
            if (edited[0] == 'sent') {
              data.editedSent = edited[1];
            } else if (edited[0] == 'equiv') { // [equiv, Equiv, T1]
              data.editedSent = null;
              $.each(data.equivs, function(equivNo, equiv) {
                if (equiv[1] == edited[1]) {
                  var len = equiv.length;
                  for (var i = 2; i < len; i++) {
                    if (equiv[i] == edited[2]) {
                      // found it
                      len -= 3;
                      for (var i = 1; i <= len; i++) {
                        var arc = data.eventDescs[equiv[0] + "*" + i].equivArc;
                        arc.edited = true;
                      }
                      return; // next equiv
                    }
                  }
                }
              });
            } else {
              data.editedSent = null;
              var span = data.spans[edited[0]];
              if (span) {
                if (edited.length == 3) { // arc
                  $.each(span.outgoing, function(arcNo, arc) {
                    if (arc.target == edited[2] && arc.type == edited[1]) {
                      arc.edited = true;
                    }
                  });
                } else { // span
                  span.edited = true;
                }
              }
            }
          });
        }

        // sort the spans for linear order
        sortedSpans.sort(function(a, b) {
          var tmp = a.from + a.to - b.from - b.to;
          if (tmp) {
            return tmp < 0 ? -1 : 1;
          }
          return 0;
        });

        // mark curlies where needed
        var lastSpan = null;
        var towerId = 0;
        $.each(sortedSpans, function(i, span) {
          if (!lastSpan || (lastSpan.from != span.from || lastSpan.to != span.to)) {
            towerId++;
          }
          span.towerId = towerId;
          span.avgDist = span.totalDist / span.numArcs;
          lastSpan = span;
        }); // sortedSpans

        var spanAnnTexts = {};
        data.spanAnnTexts = [];
        data.towers = {};

        var sortComparator = function(a, b) {
          // longer arc distances go last
          var tmp = a.avgDist - b.avgDist;
          if (tmp) {
            return tmp < 0 ? -1 : 1;
          }
          // spans with more arcs go last
          var tmp = a.numArcs - b.numArcs;
          if (tmp) {
            return tmp < 0 ? -1 : 1;
          }
          // compare the span widths,
          // put wider on bottom so they don't mess with arcs, or shorter
          // on bottom if there are no arcs.
          var ad = a.to - a.from;
          var bd = b.to - b.from;
          tmp = ad - bd;
          if(a.numArcs == 0 && b.numArcs == 0) {
              tmp = -tmp;
          } 
          if (tmp) {
            return tmp < 0 ? 1 : -1;
          }
          tmp = a.refedIndexSum - b.refedIndexSum;
          if (tmp) {
            return tmp < 0 ? -1 : 1;
          }
          // if no other criterion is found, sort by type to maintain
          // consistency
          // TODO: isn't there a cmp() in JS?
          if (a.type < b.type) {
            return -1;
          } else if (a.type > b.type) {
            return 1;
          }
          
          return 0;
        };

        for (var i = 0; i < 2; i++) {
          // preliminary sort to assign heights for basic cases
          // (first round) and cases resolved in the previous
          // round(s).
          $.each(data.chunks, function(chunkNo, chunk) {
            chunk.spans.sort(sortComparator); // sort
            $.each(chunk.spans, function(spanNo, span) {
              span.indexNumber = spanNo;
              span.refedIndexSum = 0;
            });
          });
          // resolved cases will now have indexNumber set
          // to indicate their relative order. Sum those for referencing cases
          $.each(data.arcs, function(arcNo, arc) {
            data.spans[arc.origin].refedIndexSum += data.spans[arc.target].indexNumber;
          });
        }

        // Sort spans in chunks for drawing purposes
        $.each(data.chunks, function(chunkNo, chunk) {
          // and make the next sort take this into account. Note that this will
          // now resolve first-order dependencies between sort orders but not
          // second-order or higher.
          chunk.spans.sort(sortComparator); // sort
          $.each(chunk.spans, function(spanNo, span) {
            span.chunk = chunk;
            span.text = chunk.text.substring(span.from, span.to);
            if (!data.towers[span.towerId]) {
              data.towers[span.towerId] = [];
              span.drawCurly = true;
            }
            data.towers[span.towerId].push(span);

            // Find the most appropriate abbreviation according to text
            // width
            span.abbrevText = span.type;
            var abbrevIdx = 0;
            var maxLength = (span.to - span.from) / 0.8;
            while (span.abbrevText.length > maxLength &&
                abbrevs[span.type] &&
                abbrevs[span.type][abbrevIdx]) {
              span.abbrevText = abbrevs[span.type][abbrevIdx];
              abbrevIdx++;
            }

            if (!spanAnnTexts[span.abbrevText]) {
              spanAnnTexts[span.abbrevText] = true;
              data.spanAnnTexts.push(span.abbrevText);
            }
          }); // chunk.spans
        }); // chunks

        var realSpanNo = -1;
        var lastSpan;
        $.each(sortedSpans, function(spanNo, span) {
          if (!lastSpan || span.from != lastSpan.from || span.to != lastSpan.to) realSpanNo++;
          span.lineIndex = realSpanNo;
          if (span.chunk.firstSpanIndex == undefined) span.chunk.firstSpanIndex = realSpanNo;
          span.chunk.lastSpanIndex = realSpanNo;
          lastSpan = span;
        });
      };

      var placeReservation = function(span, box, reservations) {
        var newSlot = {
          from: box.x,
          to: box.x + box.width,
          span: span,
          height: box.height + (span.drawCurly ? curlyHeight : 0),
        };
        // TODO look at this, and remove if ugly
        // example where it matters: the degenerate case of
        // http://www-tsujii.is.s.u-tokyo.ac.jp/GENIA/SharedTask/goran/visual/annotator.xhtml#miwa-genia-dev/9794389
        // (again, it would be solved by individual box reservations instead
        // of row-based)
        
        // overlapping curly check: TODO delete or uncomment
        /*
        if (span.drawCurly) {
          if (span.curly.from < newSlot.from) newSlot.from = span.curly.from;
          if (span.curly.to > newSlot.to) newSlot.to = span.curly.to;
        }
        */
        var height = 0;
        if (reservations.length) {
          for (var resNo = 0, resLen = reservations.length; resNo < resLen; resNo++) {
            var reservation = reservations[resNo];
            var line = reservation.ranges;
            height = reservation.height;
            var overlap = false;
            $.each(line, function(slotNo, slot) {
              var slot = line[slotNo];
              // with the curly change above, we can live with sharing
              // borders
              if (slot.from < newSlot.to && newSlot.from < slot.to) {
                overlap = true;
                return false;
              }
            });
            if (!overlap) {
              if (!reservation.curly && span.drawCurly) {
                // TODO: need to push up the boxes drawn so far
                // (rare glitch)
                // it would be prettier to track individual boxes (and not
                // rows) but the cases when it matters are rare, and not
                // worth the bother so far
                reservation.height += curlyHeight;
              }
              line.push(newSlot);
              return reservation.height;
            }
          }
          height += newSlot.height + boxSpacing; 
        }
        reservations.push({
          ranges: [newSlot],
          height: height,
          curly: span.drawCurly,
        });
        return height;
      };

      var translate = function(element, x, y) {
        $(element.group).attr('transform', 'translate(' + x + ', ' + y + ')');
        element.translation = { x: x, y: y };
      };

      var drawing = false;
      var redraw = false;

      var renderDataReal = function(_data) {
        if (!_data && !data) return;
        try {
          svgContainer.show();
          if (_data && (_data.document !== doc || _data.directory !== dir)) return;
          if (drawing) {
            redraw = true;
            return;
          }
          redraw = false;
          drawing = true;

          try {
            if (_data) setData(_data);

            if (data.mtime) {
                // we're getting seconds and need milliseconds
                //$('#document_ctime').text("Created: " + Annotator.formatTime(1000 * data.ctime)).css("display", "inline");
                $('#document_mtime').text("Last modified: " + Utility.formatTimeAgo(1000 * data.mtime)).css("display", "inline");
            } else {
                //$('#document_ctime').css("display", "none");
                $('#document_mtime').css("display", "none");
            }

            svg.clear(true);
            var defs = svg.defs();
            var filter = $('<filter id="Gaussian_Blur"><feGaussianBlur in="SourceGraphic" stdDeviation="2" /></filter>');
            svg.add(defs, filter);
            if (!data || data.length == 0) return;
            canvasWidth = that.forceWidth || svgContainer.width();
            svgElement.width(canvasWidth);
            var commentName = (dir + '/' + doc).replace('--', '-\\-');
            svgElement.
                attr('width', canvasWidth).
                append('<!-- document: ' + commentName + ' -->');
            
            // set up the text element, find out font height
            var backgroundGroup = svg.group({ 'class': 'background' });
            highlightGroup = svg.group({ 'class': 'highlight' });
            var textGroup = svg.group({ 'class': 'text' });
            var textSpans = svg.createText();
            $.each(data.chunks, function(chunkNo, chunk) {
              chunk.row = undefined; // reset
              textSpans.span(chunk.text + ' ', {
                  id: 'chunk' + chunk.index,
                  'data-chunk-id': chunk.index,
              });
            });
            var text = svg.text(textGroup, 0, 0, textSpans, {'class': 'text'});
            var textHeight = text.getBBox().height;

            // measure annotations
            var dummySpan = svg.group({ 'class': 'span' });
            var spanAnnBoxes = {};
            $.each(data.spanAnnTexts, function(textNo, text) {
              var spanText = svg.text(dummySpan, 0, 0, text);
              spanAnnBoxes[text] = spanText.getBBox();
            }); // data.spanAnnTexts
            svg.remove(dummySpan);

            // find biggest annotation in each tower
            $.each(data.towers, function(towerNo, tower) {
              var biggestBox = { width: 0 };
              $.each(tower, function(spanNo, span) {
                var annBox = spanAnnBoxes[span.abbrevText];
                if (annBox.width > biggestBox.width) biggestBox = annBox;
              }); // tower
              $.each(tower, function(spanNo, span) {
                span.annBox = biggestBox;
              }); // tower
            }); // data.towers

            var current = { x: margin.x + sentNumMargin + rowPadding, y: margin.y }; // TODO: we don't need some of this?
            var rows = [];
            var spanHeights = [];
            var sentenceToggle = 0;
            var sentenceNumber = 0;
            var row = new Row();
            row.sentence = ++sentenceNumber;
            row.backgroundIndex = sentenceToggle;
            row.index = 0;
            var rowIndex = 0;
            var reservations;
            var lastBoxChunkIndex = -1;
            curlyY = 0;

            $.each(data.chunks, function(chunkNo, chunk) {
              reservations = new Array();
              chunk.group = svg.group(row.group);

              var y = 0;
              var minArcDist;
              var lastArcBorder = 0;
              var hasLeftArcs, hasRightArcs, hasInternalArcs;
              var hasAnnotations;

              $.each(chunk.spans, function(spanNo, span) {
                span.group = svg.group(chunk.group, {
                  'class': 'span',
                  id: 'span_' + span.id,
                });

                // measure the text span
                var xFrom = 0;
                if (span.from != chunk.from) {
                  var measureText = svg.text(textGroup, 0, 0,
                    chunk.text.substr(0, span.from - chunk.from));
                  xFrom = measureText.getBBox().width;
                  svg.remove(measureText);
                }
                measureText = svg.text(textGroup, 0, 0,
                  chunk.text.substr(0, span.to - chunk.from));
                var measureBox = measureText.getBBox();
                if (!y) y = -textHeight - curlyHeight;
                var xTo = measureBox.width;
                span.curly = {
                  from: xFrom,
                  to: xTo,
                  height: measureBox.height,
                };
                curlyY = measureBox.y,
                svg.remove(measureText);
                var x = (xFrom + xTo) / 2;

                var spanBox = span.annBox;
                var xx = spanBox.x + x;
                var yy = spanBox.y + y;
                var hh = spanBox.height;

                // text margin fine-tuning
                yy += boxTextMargin.y;
                hh -= 2*boxTextMargin.y;
                
                var rectClass = 'span_' + span.type + ' span_default';

               // attach e.g. "False_positive" into the type
               if (span.info && span.info.type) { rectClass += ' '+span.info.type; }
               var bx = xx - margin.x - boxTextMargin.x;
               var by = yy - margin.y;
               var bw = spanBox.width + 2 * margin.x + 2 * boxTextMargin.x;
               var bh = hh + 2 * margin.y;
               var shadowRect;
               var editedRect;
               if (span.edited) {
                   editedRect = svg.rect(span.group,
                       bx - editedSpanSize, by - editedSpanSize,
                       bw + 2 * editedSpanSize, bh + 2 * editedSpanSize, {

                       // filter: 'url(#Gaussian_Blur)',
                       'class': "shadow_EditHighlight",
                       rx: editedSpanSize,
                       ry: editedSpanSize,
                   });
               }
               if (span.shadowClass) {
                   shadowRect = svg.rect(span.group,
                       bx - shadowSize, by - shadowSize,
                       bw + 2 * shadowSize, bh + 2 * shadowSize, {

                       filter: 'url(#Gaussian_Blur)',
                       'class': "shadow_" + span.shadowClass,
                       rx: shadowSize,
                       ry: shadowSize,
                   });
               }
               span.rect = svg.rect(span.group,
                   bx, by, bw, bh, {
                   'class': rectClass,
                   rx: margin.x,
                   ry: margin.y,
                   'data-span-id': span.id,
                   'strokeDashArray': span.Speculation ? dashArray : undefined,
                 });
                var rectBox = span.rect.getBBox();

                var yAdjust = placeReservation(span, rectBox, reservations);
                // this is monotonous due to sort:
                span.height = yAdjust + hh + 3 * margin.y + curlyHeight + arcSpacing;
                spanHeights[span.lineIndex * 2] = span.height;
                $(span.rect).attr('y', yy - margin.y - yAdjust);
                if (shadowRect) {
                    $(shadowRect).attr('y', yy - shadowSize - margin.y - yAdjust);
                }
                if (editedRect) {
                    $(editedRect).attr('y', yy - editedSpanSize - margin.y - yAdjust);
                }
                if (span.Negation) {
                  svg.path(span.group, svg.createPath().
                      move(xx, yy - margin.y - yAdjust).
                      line(xx + spanBox.width,
                        yy + hh + margin.y - yAdjust),
                      { 'class': 'negation' });
                  svg.path(span.group, svg.createPath().
                      move(xx + spanBox.width, yy - margin.y - yAdjust).
                      line(xx, yy + hh + margin.y - yAdjust),
                      { 'class': 'negation' });
                }
                var spanText = svg.text(span.group, x, y - yAdjust, span.abbrevText);

                // Make curlies to show the span
                if (span.drawCurly) {
                  var bottom = yy + hh + margin.y - yAdjust;
                  svg.path(span.group, svg.createPath()
                      .move(xFrom, bottom + curlyHeight)
                      .curveC(xFrom, bottom,
                        x, bottom + curlyHeight,
                        x, bottom)
                      .curveC(x, bottom + curlyHeight,
                        xTo, bottom,
                        xTo, bottom + curlyHeight),
                    {
                  });
                }

                // find the last arc backwards
                $.each(span.incoming, function(arcId, arc) {
                  var origin = data.spans[arc.origin].chunk;
                  if (chunk.index == origin.index) {
                    hasInternalArcs = true;
                  }
                  if (origin.row) {
                    hasLeftArcs = true;
                    if (origin.row.index == rowIndex) {
                      // same row, but before this
                      var border = origin.translation.x + origin.box.x + origin.box.width;
                      if (border > lastArcBorder) lastArcBorder = border;
                    }
                  } else {
                    hasRightArcs = true;
                  }
                });
                $.each(span.outgoing, function(arcId, arc) {
                  var target = data.spans[arc.target].chunk;
                  if (target.row) {
                    hasLeftArcs = true;
                    if (target.row.index == rowIndex) {
                      // same row, but before this
                      var border = target.translation.x + target.box.x + target.box.width;
                      if (border > lastArcBorder) lastArcBorder = border;
                    }
                  } else {
                    hasRightArcs = true;
                  }
                });
                hasAnnotations = true;
              }); // spans

              if (chunk.newSentence) sentenceToggle = 1 - sentenceToggle;

              chunk.tspan = $('#' + 'chunk' + chunk.index);

              // positioning of the chunk
              var spacing;
              var chunkBox = chunk.box = chunk.group.getBBox();
              var measureText = svg.text(textGroup, 0, 0, chunk.text);
              var textBox = measureText.getBBox();
              svg.remove(measureText);
              if (!chunkBox) { // older Firefox bug
                chunkBox = { x: 0, y: 0, height: 0, width: 0 };
              }
              chunkBox.height += textBox.height;
              var boxX = -Math.min(chunkBox.x, textBox.x);
              var boxWidth =
                  Math.max(textBox.x + textBox.width, chunkBox.x + chunkBox.width) -
                  Math.min(textBox.x, chunkBox.x)

              if (hasLeftArcs) {
                var spacing = arcHorizontalSpacing - (current.x - lastArcBorder);
                // arc too small?
                if (spacing > 0) current.x += spacing;
              }
              var rightBorderForArcs = hasRightArcs ? arcHorizontalSpacing : (hasInternalArcs ? arcSlant : 0);

              if (chunk.lineBreak ||
                  current.x + boxWidth + rightBorderForArcs >= canvasWidth - 2 * margin.x) {
                row.arcs = svg.group(row.group, { 'class': 'arcs' });
                // new row
                rows.push(row);
                current.x = margin.x + sentNumMargin + rowPadding +
                    (hasLeftArcs ? arcHorizontalSpacing : (hasInternalArcs ? arcSlant : 0));
                svg.remove(chunk.group);
                row = new Row();
                row.backgroundIndex = sentenceToggle;
                lastBoxChunkIndex = chunk.index - 1;
                row.index = ++rowIndex;
                svg.add(row.group, chunk.group);
                chunk.group = row.group.lastElementChild;
                $(chunk.group).children("g[class='span']").
                  each(function(index, element) {
                      chunk.spans[index].group = element;
                  });
                $(chunk.group).find("rect[data-span-id]").
                  each(function(index, element) {
                      chunk.spans[index].rect = element;
                  });
              }
              if (hasAnnotations) row.hasAnnotations = true;
              if (chunk.newSentence) row.sentence = ++sentenceNumber;

              if (spacing > 0) {
                // if we added a gap, center the intervening elements
                spacing /= 2;
                while (++lastBoxChunkIndex < chunk.index) {
                  var movedChunk = data.chunks[lastBoxChunkIndex];
                  translate(movedChunk, movedChunk.translation.x + spacing, 0);
                }
              }
              if (chunk.spans.length) lastBoxChunkIndex = chunk.index;

              row.chunks.push(chunk);
              chunk.row = row;

              translate(chunk, current.x + boxX, 0);
              chunk.textX = current.x - textBox.x + boxX;

              current.x += space + boxWidth;
            }); // chunks

            // finish the last row
            row.arcs = svg.group(row.group, { 'class': 'arcs' });
            rows.push(row);

            var arrows = {};

            var len = spanHeights.length;
            for (var i = 0; i < len; i++) {
              if (!spanHeights[i] || spanHeights[i] < arcStartHeight) spanHeights[i] = arcStartHeight;
            }

            // find out how high the arcs have to go
            $.each(data.arcs, function(arcNo, arc) {
              arc.jumpHeight = 0;
              var fromSpan = data.spans[arc.origin];
              var toSpan = data.spans[arc.target];
              if (fromSpan.lineIndex > toSpan.lineIndex) {
                var tmp = fromSpan; fromSpan = toSpan; toSpan = tmp;
              }
              var from, to;
              if (fromSpan.chunk.index == toSpan.chunk.index) {
                from = fromSpan.lineIndex;
                to = toSpan.lineIndex;
              } else {
                from = fromSpan.lineIndex + 1;
                to = toSpan.lineIndex - 1;
              }
              for (var i = from; i <= to; i++) {
                if (arc.jumpHeight < spanHeights[i * 2]) arc.jumpHeight = spanHeights[i * 2];
              }
            });

            // sort the arcs
            data.arcs.sort(function(a, b) {
              // first write those that have less to jump over
              var tmp = a.jumpHeight - b.jumpHeight;
              if (tmp) return tmp < 0 ? -1 : 1;
              // if equal, then those that span less distance
              tmp = a.dist - b.dist;
              if (tmp) return tmp < 0 ? -1 : 1;
              // if equal, then those where heights of the targets are smaller
              tmp = data.spans[a.origin].height + data.spans[a.target].height -
                data.spans[b.origin].height - data.spans[b.target].height;
              if (tmp) return tmp < 0 ? -1 : 1;
              // if equal, then those with the lower origin
              tmp = data.spans[a.origin].height - data.spans[b.origin].height;
              if (tmp) return tmp < 0 ? -1 : 1;
              // if equal, they're just equal.
              return 0;
            });

            // draw the drag arc marker
            var arrowhead = svg.marker(defs, 'drag_arrow',
              5, 2.5, 5, 5, 'auto',
              {
                markerUnits: 'strokeWidth',
                'class': 'drag_fill',
              });
            svg.polyline(arrowhead, [[0, 0], [5, 2.5], [0, 5], [0.2, 2.5]]);

            // add the arcs
            $.each(data.arcs, function(arcNo, arc) {
              roleClass = 'role_' + arc.type;

              if (!arrows[arc.type]) {
                var arrowId = 'arrow_' + arc.type;
                var arrowhead = svg.marker(defs, arrowId,
                  5, 2.5, 5, 5, 'auto',
                  {
                    markerUnits: 'strokeWidth',
                    'class': 'fill_' + arc.type,
                  });
                svg.polyline(arrowhead, [[0, 0], [5, 2.5], [0, 5], [0.2, 2.5]]);

                arrows[arc.type] = arrowId;
              }

              var originSpan = data.spans[arc.origin];
              var targetSpan = data.spans[arc.target];

              var leftToRight = originSpan.lineIndex < targetSpan.lineIndex;
              var left, right;
              if (leftToRight) {
                left = originSpan;
                right = targetSpan;
              } else {
                left = targetSpan;
                right = originSpan;
              }
              var leftBox = rowBBox(left);
              var rightBox = rowBBox(right);
              var leftRow = left.chunk.row.index;
              var rightRow = right.chunk.row.index;

              // find the next height
              var height = 0;

              var fromIndex2, toIndex2;
              if (left.chunk.index == right.chunk.index) {
                fromIndex2 = left.lineIndex * 2;
                toIndex2 = right.lineIndex * 2;
              } else {
                fromIndex2 = left.lineIndex * 2 + 1;
                toIndex2 = right.lineIndex * 2 - 1;
              }
              for (var i = fromIndex2; i <= toIndex2; i++) {
                if (spanHeights[i] > height) height = spanHeights[i];
              }
              height += arcSpacing;
              var leftSlantBound, rightSlantBound;
              for (var i = fromIndex2; i <= toIndex2; i++) {
                if (spanHeights[i] < height) spanHeights[i] = height;
              }

              var chunkReverse = false;
              var ufoCatcher = originSpan.chunk.index == targetSpan.chunk.index;
              if (ufoCatcher) {
                chunkReverse =
                  leftBox.x + leftBox.width / 2 < rightBox.x + rightBox.width / 2;
              }
              var ufoCatcherMod = ufoCatcher ? chunkReverse ? -0.5 : 0.5 : 1;

              for (var rowIndex = leftRow; rowIndex <= rightRow; rowIndex++) {
                var row = rows[rowIndex];
                row.hasAnnotations = true;
                var arcGroup = svg.group(row.arcs, {
                    'data-from': arc.origin,
                    'data-to': arc.target
                });
                var from, to;
                
                if (rowIndex == leftRow) {
                  from = leftBox.x + (chunkReverse ? 0 : leftBox.width);
                } else {
                  from = sentNumMargin;
                }

                if (rowIndex == rightRow) {
                  to = rightBox.x + (chunkReverse ? rightBox.width : 0);
                } else {
                  to = canvasWidth - 2 * margin.y;
                }

                var abbrevText = arc.type;
                var abbrevIdx = 0;
                var maxLength = ((to - from) - (2 * arcSlant)) / 7;
                while (abbrevText.length > maxLength &&
                       abbrevs[arc.type] &&
                       abbrevs[arc.type][abbrevIdx]) {
                  abbrevText = abbrevs[arc.type][abbrevIdx];
                  abbrevIdx++;
                }

                var shadowGroup;
                if (arc.shadowClass || arc.edited) shadowGroup = svg.group(arcGroup);
                var options = {
                  'class': 'fill_' + arc.type,
                  'data-arc-role': arc.type,
                  'data-arc-origin': arc.origin,
                  'data-arc-target': arc.target,
                };
                if (arc.equiv) {
                  options['data-arc-ed'] = arc.eventDescId;
                }
                var text = svg.text(arcGroup, (from + to) / 2, -height, abbrevText, options);
                var textBox = text.getBBox();
                if (arc.edited) {
                  svg.rect(shadowGroup,
                      textBox.x - editedArcSize, textBox.y - editedArcSize,
                      textBox.width + 2 * editedArcSize, textBox.height + 2 * editedArcSize, {
                        // filter: 'url(#Gaussian_Blur)',
                        'class': "shadow_EditHighlight",
                        rx: editedArcSize,
                        ry: editedArcSize,
                  });
                }
                if (arc.shadowClass) {
                  svg.rect(shadowGroup,
                      textBox.x - shadowSize, textBox.y - shadowSize,
                      textBox.width + 2 * shadowSize, textBox.height + 2 * shadowSize, {
                        filter: 'url(#Gaussian_Blur)',
                        'class': "shadow_" + arc.shadowClass,
                        rx: shadowSize,
                        ry: shadowSize,
                  });
                }
                var textStart = textBox.x - margin.x;
                var textEnd = textStart + textBox.width + 2 * margin.x;
                if (from > to) {
                  var tmp = textStart; textStart = textEnd; textEnd = tmp;
                }

                var path;
                path = svg.createPath().move(textStart, -height);
                if (rowIndex == leftRow) {
                    var cornerx = from + ufoCatcherMod * arcSlant;
                    // for normal cases, should not be past textStart even if narrow
                    if (!ufoCatcher && cornerx > textStart) { cornerx = textStart; }
                    if (smoothArcCurves) {
                        var controlx = ufoCatcher ? cornerx + 2*ufoCatcherMod*reverseArcControlx : smoothArcSteepness*from+(1-smoothArcSteepness)*cornerx;
                        line = path.line(cornerx, -height).
                            curveQ(controlx, -height, from, leftBox.y + (leftToRight || arc.equiv ? leftBox.height / 2 : margin.y));
                    } else {
                        path.line(cornerx, -height).
                            line(from, leftBox.y + (leftToRight || arc.equiv ? leftBox.height / 2 : margin.y));
                    }
                } else {
                    path.line(from, -height);
                }
                svg.path(arcGroup, path, {
                    markerEnd: leftToRight || arc.equiv ? undefined : ('url(#' + arrows[arc.type] + ')'),
                    'class': 'stroke_' + arc.type,
                    'strokeDashArray': arc.equiv ? dashArray : undefined,
                });
                if (arc.edited) {
                  svg.path(shadowGroup, path, {
                      'class': 'shadow_EditHighlight_arc',
                      strokeWidth: editedStroke,
                  });
                }
                if (arc.shadowClass) {
                  svg.path(shadowGroup, path, {
                      'class': 'shadow_' + arc.shadowClass,
                      strokeWidth: shadowStroke,
                  });
                }
                path = svg.createPath().move(textEnd, -height);
                if (rowIndex == rightRow) {
                    // TODO: duplicates above in part, make funcs
                    var cornerx  = to - ufoCatcherMod * arcSlant;
                    // for normal cases, should not be past textEnd even if narrow
                    if (!ufoCatcher && cornerx < textEnd) { cornerx = textEnd; }
                    if (smoothArcCurves) {
                        var controlx = ufoCatcher ? cornerx - 2*ufoCatcherMod*reverseArcControlx : smoothArcSteepness*to+(1-smoothArcSteepness)*cornerx;
                        path.line(cornerx, -height).
                            curveQ(controlx, -height, to, rightBox.y + (leftToRight && !arc.equiv ? margin.y : rightBox.height / 2));
                    } else {
                        path.line(cornerx, -height).
                            line(to, rightBox.y + (leftToRight && !arc.equiv ? margin.y : rightBox.height / 2));
                    }
                } else {
                  path.line(to, -height);
                }
                svg.path(arcGroup, path, {
                    markerEnd: leftToRight && !arc.equiv ? 'url(#' + arrows[arc.type] + ')' : undefined,
                    'class': 'stroke_' + arc.type,
                    'strokeDashArray': arc.equiv ? dashArray : undefined,
                });
                if (arc.edited) {
                  svg.path(shadowGroup, path, {
                      'class': 'shadow_EditHighlight_arc',
                      strokeWidth: editedStroke,
                  });
                }
                if (shadowGroup) {
                  svg.path(shadowGroup, path, {
                      'class': 'shadow_' + arc.shadowClass,
                      strokeWidth: shadowStroke,
                  });
                }
              } // arc rows
            }); // arcs

            // position the rows
            var y = margin.y;
            var sentNumGroup = svg.group({'class': 'sentnum'});
            var currentSent;
            $.each(rows, function(rowId, row) {
              if (row.sentence) {
                currentSent = row.sentence;
              }
              var rowBox = row.group.getBBox();
              if (!rowBox) { // older Firefox bug
                rowBox = { x: 0, y: 0, height: 0, width: 0 };
              }
              if (row.hasAnnotations) {
                rowBox.height = -rowBox.y+rowSpacing;
              }
              rowBox.height += rowPadding;
              svg.rect(backgroundGroup,
                0, y + curlyY + textHeight,
                canvasWidth, rowBox.height + textHeight + 1, {
                'class': 'background' +
                    (data.editedSent && data.editedSent == currentSent ?
                     'Highlight' : row.backgroundIndex),
              });
              y += rowBox.height;
              y += textHeight;
              row.textY = y - rowPadding;
              if (row.sentence) {
                var text = svg.text(sentNumGroup, sentNumMargin - margin.x, y - rowPadding,
                    '' + row.sentence, { 'data-sent': row.sentence });
                var sentInfo = data.sentInfo[row.sentence];
                if (sentInfo) {
                  var box = text.getBBox();
                  svg.remove(text);
                  shadowRect = svg.rect(sentNumGroup,
                      box.x - shadowSize, box.y - shadowSize,
                      box.width + 2 * shadowSize, box.height + 2 * shadowSize, {

                      filter: 'url(#Gaussian_Blur)',
                      'class': "shadow_" + sentInfo.type,
                      rx: shadowSize,
                      ry: shadowSize,
                      'data-sent': row.sentence,
                  });
                  var text = svg.text(sentNumGroup, sentNumMargin - margin.x, y - rowPadding,
                      '' + row.sentence, { 'data-sent': row.sentence });
                }
              }
              translate(row, 0, y - rowPadding);
              y += margin.y;
            });
            y += margin.y;

            $.each(data.chunks, function(chunkNo, chunk) {
                // text positioning
                chunk.tspan.attr({
                    x: chunk.textX,
                    y: chunk.row.textY,
                });
                // chunk backgrounds
                if (chunk.spans.length) {
                  var spansFrom, spansTo, spansType;	 
                  $.each(chunk.spans, function(spanNo, span) {
                    if (spansFrom == undefined || spansFrom > span.curly.from) spansFrom = span.curly.from;
                    if (spansTo == undefined || spansTo < span.curly.to) spansTo = span.curly.to;
                    if (span.generalType == 'trigger' || !spansType) spansType = span.type;
                  });
                  svg.rect(highlightGroup,
                    chunk.textX + spansFrom - 1, chunk.row.textY + curlyY - 1,
                    spansTo - spansFrom + 2, chunk.spans[0].curly.height + 2,
                    { 'class': 'span_default span_' + spansType, opacity:0.15 });
                }
            });

            svg.path(sentNumGroup, svg.createPath().
              move(sentNumMargin, 0).
              line(sentNumMargin, y));
            // resize the SVG
            $(svg._svg).attr('height', y).css('height', y);
            svgContainer.attr('height', y).css('height', y);

            drawing = false;
            if (redraw) {
              redraw = false;
              renderDataReal();
            }
          } catch(x) {
            if (x === 'BadDocumentError') {
              clearSVG();
              drawing = false;
            } else {
              console.error('FIXME Error during rendering: ', x); // FIXME
            }
          }
        } finally {
          dispatcher.post('doneRendering', [dir, doc, args]);
        }
      };

      var renderData = function(_data) {
        if (_data && _data.exception) {
          dispatcher.post('noFileSpecified');
        } else {
          dispatcher.post('startedRendering', [dir, doc, args]);
          dispatcher.post('spin');
          setTimeout(function() {
              renderDataReal(_data);
              dispatcher.post('unspin');
          }, 0);
        }
      };

      var renderDocument = function() {
        dispatcher.post('ajax', [{
            action: 'getDocument',
            directory: dir,
            'document': doc,
          }, 'renderData', {
            directory: dir,
            'document': doc
          }]);
      };

      var triggerRender = function() {
        if (svg && isRenderRequested && isDirLoaded) {
          isRenderRequested = false;
          if (doc.length) {
            renderDocument();
          } else {
            dispatcher.post(0, 'noFileSpecified');
          }
        }
      };
      
      var dirChanged = function() {
        isDirLoaded = false;
      };

      var dirLoaded = function(response) {
        if (!response.exception) {
          abbrevs = response.abbrevs;
          isDirLoaded = true;
          triggerRender();
        }
      };

      var gotCurrent = function(_dir, _doc, _args, reloadData) {
        dir = _dir;
        doc = _doc;
        args = _args;
        if (reloadData) {
          isRenderRequested = true;
          triggerRender();
        }
      };


      // event handlers

      var highlight, highlightArcs, highlightSpans, infoId;

      var onMouseOver = function(evt) {
        var target = $(evt.target);
        var id;
        if (id = target.attr('data-span-id')) {
          infoId = id;
          var span = data.spans[id];
          var mods = [];
          if (span.Negation) mods.push("Negated");
          if (span.Speculation) mods.push("Speculated");
          dispatcher.post('displaySpanInfo', [
              evt, target, id, span.type, mods,
              data.text.substring(span.from, span.to),
              span.info && span.info.text,
              span.info && span.info.type]);
          highlight = svg.rect(highlightGroup,
            span.chunk.textX + span.curly.from - 1, span.chunk.row.textY + curlyY - 1,
            span.curly.to + 2 - span.curly.from, span.curly.height + 2,
            { 'class': 'span_default span_' + span.type });

          if (that.arcDragOrigin) {
            target.parent().addClass('highlight');
          } else {
            highlightArcs = svgElement.
                find('g[data-from="' + id + '"], g[data-to="' + id + '"]').
                addClass('highlight');
            var spans = {};
            spans[id] = true;
            var spanIds = [];
            $.each(span.incoming, function(arcNo, arc) {
                spans[arc.origin] = true;
            });
            $.each(span.outgoing, function(arcNo, arc) {
                spans[arc.target] = true;
            });
            $.each(spans, function(spanId, dummy) {
                spanIds.push('rect[data-span-id="' + spanId + '"]');
            });
            highlightSpans = svgElement.
                find(spanIds.join(', ')).
                parent().
                addClass('highlight');
          }
          forceRedraw();
        } else if (!that.arcDragOrigin && (id = target.attr('data-arc-role'))) {
          var originSpanId = target.attr('data-arc-origin');
          var targetSpanId = target.attr('data-arc-target');
          var role = target.attr('data-arc-role');
          // TODO: remove special-case processing, introduce way to differentiate
          // symmetric relations in general
          var symmetric = role === "Equiv";
          // NOTE: no infoText, infoType for now
          dispatcher.post('displayArcInfo', [
              evt, target, symmetric, 
              originSpanId, role, targetSpanId]);
          highlightArcs = $(svgElement).
              find('g[data-from="' + originSpanId + '"][data-to="' + targetSpanId + '"]').
              addClass('highlight');
          highlightSpans = $(svgElement).
              find('rect[data-span-id="' + originSpanId + '"], rect[data-span-id="' + targetSpanId + '"]').
              parent().
              addClass('highlight');
        } else if (id = target.attr('data-sent')) {
          var info = data.sentInfo[id];
          if (info) {
          // NOTE: no infoText, infoType for now
          dispatcher.post('displaySentInfo', [
              evt, target, info]);
            displaySentInfo(info.text, evt);
          }
        }
      };

      var onMouseOut = function(evt) {
        var target = $(evt.target);
        dispatcher.post('hideInfo');
        if (highlight) {
          svg.remove(highlight);
          highlight = undefined;
        }
        if (highlightSpans) {
          highlightArcs.removeClass('highlight');
          highlightSpans.removeClass('highlight');
          highlightSpans = undefined;
        }
        forceRedraw();
      };

      svgContainer = $(svgContainer).hide();

      // register event listeners
      var registerHandlers = function(element, events) {
        $.each(events, function(eventNo, eventName) {
            element.bind(eventName,
              function(evt) {
                dispatcher.post(eventName, [evt]);
              }
            );
        });
      };
      registerHandlers(svgContainer, [
          'mouseover', 'mouseout', 'mousemove',
          'mouseup', 'mousedown',
          'dblclick', 'click'
      ]);
      registerHandlers($(document), [
          'keydown', 'keypress'
      ]);
      registerHandlers($(window), [
          'resize'
      ]);

      // create the svg wrapper
      svgContainer.svg({
          onLoad: function(_svg) {
              that.svg = svg = _svg;
              svgElement = $(svg._svg);
              triggerRender();
          }
      });

      dispatcher.
          on('dirChanged', dirChanged).
          on('dirLoaded', dirLoaded).
          on('renderData', renderData).
          on('current', gotCurrent).
          on('mouseover', onMouseOver).
          on('mouseout', onMouseOut);
    };

    return Visualizer;
})(jQuery, window);
