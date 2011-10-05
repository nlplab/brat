// vim:set ft=javascript ts=2 sw=2 sts=2 cindent:


var Visualizer = (function($, window, undefined) {
    var Span = function(id, type, from, to, generalType) {
      this.id = id;
      this.type = type;
      this.from = parseInt(from);
      this.to = parseInt(to);
      this.outgoing = [];
      this.incoming = [];
      this.attributes = {};
      this.attributeText = [];
      this.attributeCues = {};
      this.attributeCueFor = {};
      this.attributeMerge = {}; // for box, cross, etc. that are span-global
      this.totalDist = 0;
      this.numArcs = 0;
      this.generalType = generalType;
    };

    var EventDesc = function(id, triggerId, roles, klass) {
      this.id = id;
      this.triggerId = triggerId;
      var roleList = this.roles = [];
      $.each(roles, function(roleNo, role) {
        roleList.push({ type: role[0], targetId: role[1] });
      });
      if (klass == "equiv") {
        this.equiv = true;
      } else if (klass == "relation") {
        this.relation = true;
      }
    };

    var Row = function(svg) {
      this.group = svg.group();
      this.background = svg.group(this.group);
      this.chunks = [];
      this.hasAnnotations = 0;
    };

    var Visualizer = function(dispatcher, svgId) {
      var $svgDiv = $('#' + svgId);
      var that = this;

      // OPTIONS
      var roundCoordinates = true; // try to have exact pixel offsets
      var margin = { x: 2, y: 1 };
      var boxTextMargin = { x: 0, y: 1.5 }; // effect is inverse of "margin" for some reason
      var highlightRounding = { x: 3, y:3 }; // rx, ry for highlight boxes
      var spaceWidths = {
        ' ': 4,
        '\u00a0': 4,
        '\u200b': 0,
        '\u3000': 8,
        '\n': 4
      };
      var boxSpacing = 1;
      var curlyHeight = 4;
      var arcSpacing = 9; //10;
      var arcSlant = 15; //10;
      var minArcSlant = 8;
      var arcStartHeight = 19; //23; //25;
      var arcHorizontalSpacing = 10; // min space boxes with connecting arc
      var rowSpacing = -5;          // for some funny reason approx. -10 gives "tight" packing.
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
      var nestingAdjustYStepSize = 2; // size of height adjust for nested/nesting spans
      var nestingAdjustXStepSize = 1; // size of height adjust for nested/nesting spans

      var highlightSequence = 'FFFC69;FFCC00;FFFC69';
      var highlightSpanSequence = highlightSequence;
      var highlightArcSequence =  highlightSequence;
      var highlightTextSequence = highlightSequence;
      var highlightDuration = '2s';
      
      // END OPTIONS


      var svg;
      var $svg;
      var data = null;
      var coll, doc, args;
      var spanTypes;
      var relationTypesHash;
      var abbrevsOn = true;
      var isRenderRequested;
      var isCollectionLoaded = false;
      var areFontsLoaded = false;
      var attributeTypes = null;
      var spanTypes = null;
      var highlightGroup;

      var commentPrioLevels = ['Unconfirmed', 'Incomplete', 'Warning', 'Error', 'AnnotatorNotes'];

      this.arcDragOrigin = null; // TODO

      // due to silly Chrome bug, I have to make it pay attention
      var forceRedraw = function() {
        if (!$.browser.chrome) return; // not needed
        $svg.css('margin-bottom', 1);
        setTimeout(function() { $svg.css('margin-bottom', 0); }, 0);
      }

      var rowBBox = function(span) {
        var box = $.extend({}, span.rectBox); // clone
        var chunkTranslation = span.chunk.translation;
        box.x += chunkTranslation.x;
        box.y += chunkTranslation.y;
        return box;
      };

      var commentPriority = function(commentClass) {
        if (commentClass === undefined) return -1;
        var len = commentPrioLevels.length;
        for (var i = 0; i < len; i++) {
          if (commentClass.indexOf(commentPrioLevels[i]) != -1) return i;
        }
        return 0;
      };

      var clearSVG = function() {
        svg.clear();
        $svgDiv.hide();
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
              [new Span(trigger[0], trigger[1], trigger[2], trigger[3], 'trigger'), []];
        });
        data.eventDescs = {};
        $.each(data.events, function(eventNo, eventRow) {
          var eventDesc = data.eventDescs[eventRow[0]] =
              new EventDesc(eventRow[0], eventRow[1], eventRow[2]);
          var trigger = triggerHash[eventDesc.triggerId];
          var span = $.extend({}, trigger[0]); // clone
          trigger[1].push(span);
          span.incoming = []; // protect from shallow copy
          span.outgoing = [];
          span.attributes = {};
          span.attributeText = [];
          span.attributeCues = {};
          span.attributeCueFor = {};
          span.attributeMerge = {};
          span.id = eventDesc.id;
          data.spans[eventDesc.id] = span;
        });

        // XXX modifications: delete later
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
                new EventDesc(equivSpans[i - 1], equivSpans[i - 1], [[equiv[1], equivSpans[i]]], 'equiv');
            eventDesc.leftSpans = equivSpans.slice(0, i);
            eventDesc.rightSpans = equivSpans.slice(i);
          }
        });
        $.each(data.relations, function(relNo, rel) {
          data.eventDescs[rel[0]] =
              new EventDesc(rel[2], rel[2], [[rel[1], rel[3]]], 'relation');
        });

        // attributes
        $.each(data.attributes, function(attrNo, attr) {
          var attrType = attributeTypes[attr[1]];
          var attrValue = attrType && attrType.values[attrType.bool || attr[3]];
          var span = data.spans[attr[2]];
          var valText = (attrValue && attrValue.name) || attr[3];
          var attrText = attrType
            ? (attrType.bool ? attrType.name : (attrType.name + ': ' + valText))
            : (attr[3] == true ? attr[1] : attr[1] + ': ' + attr[3]);
          span.attributeText.push(attrText);
          span.attributes[attr[1]] = attr[3];
          if (attr[4]) { // cue
            span.attributeCues[attr[1]] = attr[4];
            var cueSpan = data.spans[attr[4]];
            cueSpan.attributeCueFor[data.spans[1]] = attr[2];
            cueSpan.cue = 'CUE'; // special css type
          }
          $.extend(span.attributeMerge, attrValue);
        });

        data.sentComment = {};
        $.each(data.comments, function(commentNo, comment) {
          // TODO error handling
          if (comment[0] instanceof Array && comment[0][0] == 'sent') { // [['sent', 7], 'Type', 'Text']
            var sent = comment[0][1];
            var text = comment[2];
            if (data.sentComment[sent]) {
              text = data.sentComment[sent].text + '<br/>' + text;
            }
            data.sentComment[sent] = { type: comment[1], text: text };
          } else {
            var id = comment[0];
            var trigger = triggerHash[id];
            var eventDesc = data.eventDescs[id];
            var commentEntities =
                trigger
                ? trigger[1]
                : id in data.spans
                  ? [data.spans[id]]
                  : id in data.eventDescs
                    ? [data.eventDescs[id]]
                    : [];
            $.each(commentEntities, function(entityId, entity) {
              if (!entity.comment) {
                entity.comment = { type: comment[1], text: comment[2] };
              } else {
                entity.comment.type = comment[1];
                entity.comment.text += "\n" + comment[2];
              }
              // partially duplicate marking of annotator note comments
              if (comment[1] == "AnnotatorNotes") {
                entity.annotatorNotes = comment[2];
              }
              // prioritize type setting when multiple comments are present
              if (commentPriority(comment[1]) > commentPriority(entity.shadowClass)) {
                entity.shadowClass = comment[1];
              }
            });
          }
        });

        data.chunks = [];
        var lastTo = 0;
        var firstFrom = null;
        var chunkNo = 0;
        var inSpan;
        var space;
        var chunk = null;
        $.each(data.token_offsets, function() {
          var from = this[0];
          var to = this[1];
          if (firstFrom === null) firstFrom = from;
          inSpan = false;
          $.each(data.spans, function(spanNo, span) {
            if (span.from < to && to < span.to) {
              // it does; no word break
              inSpan = true;
              return false;
            }
          });
          if (inSpan) return;
          space = data.text.substring(lastTo, firstFrom);
          var text = data.text.substring(firstFrom, to);
          if (chunk) chunk.nextSpace = space;
          chunk = {
              text: text,
              space: space,
              from: firstFrom,
              to: to,
              index: chunkNo++,
              spans: [],
            };
          data.chunks.push(chunk);
          lastTo = to;
          firstFrom = null;
        });
        var numChunks = chunkNo;

        chunkNo = 0;
        var sentenceNo = 0;
        var pastFirst = false;
        $.each(data.sentence_offsets, function() {
          var from = this[0];
          var to = this[0];
          var chunk;
          while (chunkNo < numChunks && (chunk = data.chunks[chunkNo]).from < from) {
            chunkNo++;
          }
          chunkNo++;
          if (pastFirst) {
            var numNL = chunk.space.split("\n").length - 1;
            if (!numNL) numNL = 1;
            sentenceNo += numNL;
            chunk.sentence = sentenceNo;
          } else {
            pastFirst = true;
          }
        });

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
              shadowClass: eventDesc.shadowClass,
            };
            if (eventDesc.equiv) {
              arc.equiv = true;
              eventDesc.equivArc = arc;
              arc.eventDescId = eventNo;
            } else if (eventDesc.relation) {
              arc.relation = true;
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

        // highlighting

        // merge edited and focus fields in arguments
        // edited: set by editing process
        // focus: set by search process
        var argsEdited = (args.edited || []).concat(args.focus || []);

        data.editedSent = [];
        editedText = [];
        var setEdited = function(editedType) {
          $.each(args[editedType] || [], function(editedNo, edited) {
            if (edited[0] == 'sent') {
              data.editedSent.push(parseInt(edited[1], 10));
            } else if (edited[0] == 'equiv') { // [equiv, Equiv, T1]
              $.each(data.equivs, function(equivNo, equiv) {
                if (equiv[1] == edited[1]) {
                  var len = equiv.length;
                  for (var i = 2; i < len; i++) {
                    if (equiv[i] == edited[2]) {
                      // found it
                      len -= 3;
                      for (var i = 1; i <= len; i++) {
                        var arc = data.eventDescs[equiv[0] + "*" + i].equivArc;
                        arc.edited = editedType;
                      }
                      return; // next equiv
                    }
                  }
                }
              });
            } else if (edited.length == 2) {
              editedText.push([parseInt(edited[0], 10), parseInt(edited[1], 10)]);
            } else {
              var span = data.spans[edited[0]];
              if (span) {
                if (edited.length == 3) { // arc
                  $.each(span.outgoing, function(arcNo, arc) {
                    if (arc.target == edited[2] && arc.type == edited[1]) {
                      arc.edited = editedType;
                    }
                  });
                } else { // span
                  span.edited = editedType;
                }
              } else {
                var eventDesc = data.eventDescs[edited[0]];
                if (eventDesc) { // relation
                  var relArc = eventDesc.roles[0];
                  $.each(data.spans[eventDesc.triggerId].outgoing, function(arcNo, arc) {
                    if (arc.target == relArc.targetId && arc.type == relArc.type) {
                      arc.edited = editedType;
                    }
                  });
                } else { // try for trigger
                  $.each(data.eventDescs, function(eventDescNo, eventDesc) {
                    if (eventDesc.triggerId == edited[0]) {
                      data.spans[eventDesc.id].edited = editedType;
                    }
                  });
                }
              }
            }
          });
        };
        setEdited('edited');
        setEdited('focus');

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
        data.spanAnnTexts = {};
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

          chunk.editedTextStart = [];
          chunk.editedTextEnd = [];

          $.each(chunk.spans, function(spanNo, span) {
            span.chunk = chunk;
            // TODO: span.text is useful, but this is a weird place to init it ...
            span.text = chunk.text.substring(span.from - chunk.from, span.to - chunk.from);
            if (!data.towers[span.towerId]) {
              data.towers[span.towerId] = [];
              span.drawCurly = true;
            }
            data.towers[span.towerId].push(span);

            var spanLabels = Util.getSpanLabels(spanTypes, span.type);
            span.labelText = Util.spanDisplayForm(spanTypes, span.type);
            // Find the most appropriate label according to text width
            if (abbrevsOn && spanLabels) {
              var labelIdx = 1; // first abbrev
              var maxLength = (span.to - span.from) / 0.8;
              while (span.labelText.length > maxLength &&
                  spanLabels[labelIdx]) {
                span.labelText = spanLabels[labelIdx];
                labelIdx++;
              }
            }

            var svgtext = svg.createText();
            var postfixArray = [];
            var prefix = '';
            var postfix = '';
            var warning = false;
            $.each(span.attributes, function(attrType, valType) {
              var attr = attributeTypes[attrType];
              if (!attr) {
                // non-existent type
                warning = true;
                return;
              }
              var val = attr.values[attr.bool || valType];
              if (!val) {
                // non-existent value
                warning = true;
                return;
              }
              if (val.glyph) {
                if (val.position == "left") {
                  prefix = val.glyph + prefix;
                  var css = 'glyph';
                  if (attr.css) css += ' glyph_' + Util.escapeQuotes(attr.css);
                  svgtext.span(val.glyph, { 'class': css });
                } else { // XXX right is implied - maybe change
                  postfixArray.push([attr, val]);
                  postfix += val.glyph;
                }
              }
            });
            var text = span.labelText;
            if (prefix !== '') {
              text = prefix + ' ' + text;
              svgtext.string(' ');
            }
            svgtext.string(span.labelText);
            if (postfixArray.length) {
              text += ' ' + postfix;
              svgtext.string(' ');
              $.each(postfixArray, function(elNo, el) {
                var css = 'glyph';
                if (el[0].css) css += ' glyph_' + Util.escapeQuotes(el[0].css);
                svgtext.span(el[1].glyph, { 'class': css });
              });
            }
            if (warning) {
              svgtext.span("#", { 'class': 'glyph attribute_warning' });
            }
            span.glyphedLabelText = text;

            if (!spanAnnTexts[text]) {
              spanAnnTexts[text] = true;
              data.spanAnnTexts[text] = svgtext;
            }
          }); // chunk.spans
        }); // chunks

        var numChunks = data.chunks.length;
        $.each(editedText, function(textNo, textPos) {
          var from = textPos[0];
          var to = textPos[1];
          if (from < 0) from = 0;
          if (to < 0) to = 0;
          if (to >= data.text.length) to = data.text.length - 1;
          if (from > to) from = to;
          var i = 0;
          while (i < numChunks) {
            var chunk = data.chunks[i];
            if (from <= chunk.to) {
              chunk.editedTextStart.push([textNo, true, from - chunk.from]);
              break;
            }
            i++;
          }
          if (i == numChunks) {
            dispatcher.post('messages', [[['Wrong text offset', 'error']]]);
            return;
          }
          while (i < numChunks) {
            var chunk = data.chunks[i];
            if (to <= chunk.to) {
              chunk.editedTextEnd.push([textNo, false, to - chunk.from]);
              break
            }
            i++;
          }
          if (i == numChunks) {
            dispatcher.post('messages', [[['Wrong text offset', 'error']]]);
            var chunk = data.chunks[data.chunks.length - 1];
            chunk.editedTextEnd.push([textNo, false, chunk.text.length]);
            return;
          }
        });

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

      var resetData = function() {
        setData(data);
        renderData();
      }

      var placeReservation = function(span, x, width, height, reservations) {
        var newSlot = {
          from: x,
          to: x + width,
          span: span,
          height: height + (span.drawCurly ? curlyHeight : 0),
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
        var resHeight = 0;
        if (reservations.length) {
          for (var resNo = 0, resLen = reservations.length; resNo < resLen; resNo++) {
            var reservation = reservations[resNo];
            var line = reservation.ranges;
            resHeight = reservation.height;
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
          resHeight += newSlot.height + boxSpacing;
        }
        reservations.push({
          ranges: [newSlot],
          height: resHeight,
          curly: span.drawCurly,
        });
        return resHeight;
      };

      var translate = function(element, x, y) {
        $(element.group).attr('transform', 'translate(' + x + ', ' + y + ')');
        element.translation = { x: x, y: y };
      };

      var showMtime = function() {
        if (data.mtime) {
            // we're getting seconds and need milliseconds
            //$('#document_ctime').text("Created: " + Annotator.formatTime(1000 * data.ctime)).css("display", "inline");
            $('#document_mtime').text("Last modified: " + Util.formatTimeAgo(1000 * data.mtime)).css("display", "inline");
        } else {
            //$('#document_ctime').css("display", "none");
            $('#document_mtime').css("display", "none");
        }
      };
      
      var addHeaderAndDefs = function() {
        var commentName = (coll + '/' + doc).replace('--', '-\\-');
        $svg.append('<!-- document: ' + commentName + ' -->');
        var defs = svg.defs();
        var $blurFilter = $('<filter id="Gaussian_Blur"><feGaussianBlur in="SourceGraphic" stdDeviation="2" /></filter>');
        svg.add(defs, $blurFilter);
        return defs;
      }

      var getTextMeasurements = function(textsHash, options, callback) {
        // make some text elements, find out the dimensions
        var textMeasureGroup = svg.group(options);

        // changed from $.each because of #264 ('length' can appear)
        for (var text in textsHash) {
          if (textsHash.hasOwnProperty(text)) {
            svg.text(textMeasureGroup, 0, 0, text);
          }
        }

        // measuring goes on here
        var widths = {};
        $(textMeasureGroup).find('text').each(function(svgTextNo, svgText) {
          var text = $(svgText).text();
          widths[text] = this.getComputedTextLength();

          if (callback) {
            $.each(textsHash[text], function(text, object) {
              callback(object, svgText);
            });
          }
        });
        var bbox = textMeasureGroup.getBBox();
        svg.remove(textMeasureGroup);

        return {
          widths: widths,
          height: bbox.height,
          y: bbox.y,
        };
      };

      var getTextAndSpanTextMeasurements = function() {
        // get the span text sizes
        var chunkTexts = {}; // set of span texts
        $.each(data.chunks, function(chunkNo, chunk) {
          chunk.row = undefined; // reset
          if (!(chunk.text in chunkTexts)) chunkTexts[chunk.text] = []
          var chunkText = chunkTexts[chunk.text];

          // here we also need all the spans that are contained in
          // chunks with this text, because we need to know the position
          // of the span text within the respective chunk text
          chunkText.push.apply(chunkText, chunk.spans);
          // and also the editedText boundaries
          chunkText.push.apply(chunkText, chunk.editedTextStart);
          chunkText.push.apply(chunkText, chunk.editedTextEnd);
        });
        var textSizes = getTextMeasurements(
          chunkTexts,
          undefined,
          function(span, text) {
            if (span.text !== undefined) { // it's a span!
              // measure the span text position in pixels
              var firstChar = span.from - span.chunk.from;
              if (firstChar < 0) {
                firstChar = 0;
                console.warn("DEBUG: Span", span.text, "in chunk", span.chunk.text, "has strange offsets. FIXME");
              }
              var startPos = text.getStartPositionOfChar(firstChar).x;
              var lastChar = span.to - span.chunk.from - 1;
              var endPos = (lastChar < 0)
                ? startPos
                : text.getEndPositionOfChar(lastChar).x;
              span.curly = {
                from: startPos,
                to: endPos
              };
            } else { // it's editedText [id, start?, char#, offset]
              if (span[1] || span[2] == 0) { // start
                span[3] = text.getStartPositionOfChar(span[2]).x;
              } else {
                span[3] = text.getEndPositionOfChar(span[2] - 1).x;
              }
            }
          });

        // get the span annotation text sizes
        var spanTexts = {};
        $.each(data.spans, function(spanNo, span) {
          spanTexts[span.glyphedLabelText] = true;
        });
        var spanSizes = getTextMeasurements(spanTexts, {'class': 'span'});

        return {
          texts: textSizes,
          spans: spanSizes
        };

        // XXX NOTE
        // var textHeight = measureBox.height; // => sizes.texts.height
        // curlyY = measureBox.y;              // => sizes.texts.y
      };

      var addArcTextMeasurements = function(sizes) {
        // get the arc annotation text sizes (for all labels)
        var arcTexts = {};
        $.each(data.arcs, function(arcNo, arc) {
          var labels = Util.getArcLabels(spanTypes, data.spans[arc.origin].type, arc.type);
          if (!labels.length) labels = [arc.type];
          $.each(labels, function(labelNo, label) {
            arcTexts[label] = true;
          });
        });
        var arcSizes = getTextMeasurements(arcTexts, {'class': 'arcs'});
        sizes.arcs = arcSizes;
      };

      var adjustTowerAnnotationSizes = function() {
        // find biggest annotation in each tower
        $.each(data.towers, function(towerNo, tower) {
          var maxWidth = 0;
          $.each(tower, function(spanNo, span) {
            var width = data.sizes.spans.widths[span.glyphedLabelText];
            if (width > maxWidth) maxWidth = width;
          }); // tower
          $.each(tower, function(spanNo, span) {
            span.width = maxWidth;
          }); // tower
        }); // data.towers
      };

      var makeArrow = function(defs, spec) {
        var parsedSpec = spec.split(',');
        var type = parsedSpec[0];
        if (type == 'none') return;

        var size = parsedSpec[1];
        var color = parsedSpec[2];
        if (!color) {
          color = size;
          size = 5;
        }
        var arrowId = 'arrow_' + spec.replace(/,/g, '_');

        var arrow;
        if (type == 'triangle') {
          arrow = svg.marker(defs, arrowId,
            size, size / 2, size, size, 'auto',
            {
              markerUnits: 'strokeWidth',
              'fill': color,
            });
          svg.polyline(arrow, [[0, 0], [size, size / 2], [0, size], [size / 25, size / 2]]);
        }
        return arrowId;
      }


      var drawing = false;
      var redraw = false;

      var renderDataReal = function(_data) {

Util.profileEnd('before render');
Util.profileStart('render');
Util.profileStart('init');

        if (!_data && !data) return;
        $svgDiv.show();
        if ((_data && (_data.document !== doc || _data.collection !== coll)) || drawing) {
          redraw = true;
          dispatcher.post('doneRendering', [coll, doc, args]);
          return;
        }
        redraw = false;
        drawing = true;

        if (_data) setData(_data);
        showMtime();

        // clear the SVG
        svg.clear(true);
        if (!data || data.length == 0) return;

        // establish the width according to the enclosing element
        canvasWidth = that.forceWidth || $svgDiv.width();

        var defs = addHeaderAndDefs();

        var backgroundGroup = svg.group({ class: 'background' });
        var glowGroup = svg.group({ class: 'glow' });
        highlightGroup = svg.group({ class: 'highlight' });
        var textGroup = svg.group({ class: 'text' });

Util.profileEnd('init');
Util.profileStart('measures');

        var sizes = getTextAndSpanTextMeasurements();
        data.sizes = sizes;

        adjustTowerAnnotationSizes();
        var maxTextWidth = 0;
        $.each(sizes.texts.widths, function(text, width) {
          if (width > maxTextWidth) maxTextWidth = width;
        });

        var width = maxTextWidth + sentNumMargin + 2 * margin.x + 1;
        if (width > canvasWidth) canvasWidth = width;
        $svg.width(canvasWidth);

Util.profileEnd('measures');
Util.profileStart('chunks');

        var current = { x: margin.x + sentNumMargin + rowPadding, y: margin.y }; // TODO: we don't need some of this?
        var rows = [];
        var spanHeights = [];
        var sentenceToggle = 0;
        var sentenceNumber = 0;
        var row = new Row(svg);
        row.sentence = ++sentenceNumber;
        row.backgroundIndex = sentenceToggle;
        row.index = 0;
        var rowIndex = 0;
        var reservations;
        var twoBarWidths; // HACK to avoid measuring space's width
        var openTextHighlights = {};
        var textEditedRows = [];

        addArcTextMeasurements(sizes);
        $.each(data.chunks, function(chunkNo, chunk) {
          reservations = new Array();
          chunk.group = svg.group(row.group);
          chunk.highlightGroup = svg.group(chunk.group);

          var y = 0;
          var minArcDist;
          var hasLeftArcs, hasRightArcs, hasInternalArcs;
          var hasAnnotations;
          var chunkFrom = Infinity;
          var chunkTo = 0;
          var chunkHeight = 0;
          var spacing = 0;
          var spacingChunkId = null;
          var spacingRowBreak = 0;

          $.each(chunk.spans, function(spanNo, span) {
            var spanDesc = spanTypes[span.type];
            var bgColor = spanDesc && spanDesc.bgColor || spanTypes.SPAN_DEFAULT.bgColor || '#ffffff';
            var fgColor = spanDesc && spanDesc.fgColor || spanTypes.SPAN_DEFAULT.fgColor || '#000000';
            var borderColor = spanDesc && spanDesc.borderColor || spanTypes.SPAN_DEFAULT.borderColor || '#000000';

            // special case: if the border 'color' value is 'darken',
            // then just darken the BG color a bit for the border.
            if (borderColor == 'darken') {
                borderColor = Util.adjustColorLightness(bgColor, -0.6);
            }
            
            span.group = svg.group(chunk.group, {
              'class': 'span',
            });

            var spanHeight = 0;

            if (!y) y = -sizes.texts.height - curlyHeight;
            var x = (span.curly.from + span.curly.to) / 2;

            // XXX is it maybe sizes.texts?
            var yy = y + sizes.spans.y;
            var hh = sizes.spans.height;
            var ww = span.width;
            var xx = x - ww / 2;

            // text margin fine-tuning
            yy += boxTextMargin.y;
            hh -= 2*boxTextMargin.y;
            xx += boxTextMargin.x;
            ww -= 2*boxTextMargin.x;
            var rectClass = 'span_' + (span.cue || span.type) + ' span_default';

            // attach e.g. "False_positive" into the type
            if (span.comment && span.comment.type) { rectClass += ' '+span.comment.type; }
            var bx = xx - margin.x - boxTextMargin.x;
            var by = yy - margin.y;
            var bw = ww + 2 * margin.x;
            var bh = hh + 2 * margin.y;

            if (roundCoordinates) {
              x  = (x|0)+0.5;
              bx = (bx|0)+0.5;              
            }

            var shadowRect;
            var editedRect;
            if (span.edited) {
              editedRect = svg.rect(chunk.highlightGroup,
                  bx - editedSpanSize, by - editedSpanSize,
                  bw + 2 * editedSpanSize, bh + 2 * editedSpanSize, {
 
                  // filter: 'url(#Gaussian_Blur)',
                  'class': "shadow_EditHighlight",
                  rx: editedSpanSize,
                  ry: editedSpanSize,
              });
              svg.other(editedRect, 'animate', {
                'data-type': span.edited,
                attributeName: 'fill',
                values: highlightSpanSequence,
                dur: highlightDuration,
                repeatCount: 'indefinite',
                begin: 'indefinite'
              });
              chunkFrom = Math.min(bx - editedSpanSize, chunkFrom);
              chunkTo = Math.max(bx + bw + editedSpanSize, chunkTo);
              spanHeight = Math.max(bh + 2 * editedSpanSize, spanHeight);
            }
            if (span.shadowClass) {
              shadowRect = svg.rect(span.group,
                  bx - shadowSize, by - shadowSize,
                  bw + 2 * shadowSize, bh + 2 * shadowSize, {
                  'class': 'blur shadow_' + span.shadowClass,
                  rx: shadowSize,
                  ry: shadowSize,
              });
              chunkFrom = Math.min(bx - shadowSize, chunkFrom);
              chunkTo = Math.max(bx + bw + shadowSize, chunkTo);
              spanHeight = Math.max(bh + 2 * shadowSize, spanHeight);
            }
            span.rect = svg.rect(span.group,
                bx, by, bw, bh, {

                'class': rectClass,
                fill: bgColor,
                stroke: borderColor,
                rx: margin.x,
                ry: margin.y,
                'data-span-id': span.id,
                'strokeDashArray': span.attributeMerge.dasharray,
              });
            span.right = bx + bw; // TODO put it somewhere nicer?
            if (!(span.shadowClass || span.edited)) {
              chunkFrom = Math.min(bx, chunkFrom);
              chunkTo = Math.max(bx + bw, chunkTo);
              spanHeight = Math.max(bh, spanHeight);
            }

            var yAdjust = placeReservation(span, bx, bw, bh, reservations);
            span.rectBox = { x: bx, y: by - yAdjust, width: bw, height: bh };
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
            if (span.attributeMerge.box === "crossed") {
              svg.path(span.group, svg.createPath().
                  move(xx, yy - margin.y - yAdjust).
                  line(xx + span.width,
                    yy + hh + margin.y - yAdjust),
                  { 'class': 'boxcross' });
              svg.path(span.group, svg.createPath().
                  move(xx + span.width, yy - margin.y - yAdjust).
                  line(xx, yy + hh + margin.y - yAdjust),
                  { 'class': 'boxcross' });
            }
            var spanText = svg.text(span.group, x, y - yAdjust, data.spanAnnTexts[span.glyphedLabelText], { fill: fgColor });

            // Make curlies to show the span
            if (span.drawCurly) {
              var bottom = yy + hh + margin.y - yAdjust + 1;
              svg.path(span.group, svg.createPath()
                  .move(span.curly.from, bottom + curlyHeight)
                  .curveC(span.curly.from, bottom,
                    x, bottom + curlyHeight,
                    x, bottom)
                  .curveC(x, bottom + curlyHeight,
                    span.curly.to, bottom,
                    span.curly.to, bottom + curlyHeight),
                {
                  'class': 'curly'
              });
              chunkFrom = Math.min(span.curly.from, chunkFrom);
              chunkTo = Math.max(span.curly.to, chunkTo);
              spanHeight = Math.max(curlyHeight, spanHeight);
            }

            // find the gap to fit the backwards arcs
            $.each(span.incoming, function(arcId, arc) {
              var leftSpan = data.spans[arc.origin];
              var origin = leftSpan.chunk;
              var border;
              if (chunk.index == origin.index) {
                hasInternalArcs = true;
              }
              if (origin.row) {
                var labels = Util.getArcLabels(spanTypes, leftSpan.type, arc.type);
                if (!labels.length) labels = [arc.type];
                if (origin.row.index == rowIndex) {
                  // same row, but before this
                  border = origin.translation.x + leftSpan.right;
                } else {
                  border = margin.x + sentNumMargin + rowPadding;
                }
                var labelNo = abbrevsOn ? labels.length - 1 : 0;
                var smallestLabelWidth = sizes.arcs.widths[labels[labelNo]] + 2 * minArcSlant;
                var gap = current.x + bx - border;
                var arcSpacing = smallestLabelWidth - gap;
                if (!hasLeftArcs || spacing < arcSpacing) {
                  spacing = arcSpacing;
                  spacingChunkId = origin.index + 1;
                }
                arcSpacing = smallestLabelWidth - bx;
                if (!hasLeftArcs || spacingRowBreak < arcSpacing) {
                  spacingRowBreak = arcSpacing;
                }
                hasLeftArcs = true;
              } else {
                hasRightArcs = true;
              }
            });
            $.each(span.outgoing, function(arcId, arc) {
              var leftSpan = data.spans[arc.target];
              var target = leftSpan.chunk;
              var border;
              if (target.row) {
                var labels = Util.getArcLabels(spanTypes, span.type, arc.type);
                if (!labels.length) labels = [arc.type];
                if (target.row.index == rowIndex) {
                  // same row, but before this
                  border = target.translation.x + leftSpan.right;
                } else {
                  border = margin.x + sentNumMargin + rowPadding;
                }
                var labelNo = abbrevsOn ? labels.length - 1 : 0;
                var smallestLabelWidth = sizes.arcs.widths[foo = labels[labelNo]] + 2 * minArcSlant;
                var gap = current.x + bx - border;
                var arcSpacing = smallestLabelWidth - gap;
                if (!hasLeftArcs || spacing < arcSpacing) {
                  spacing = arcSpacing;
                  spacingChunkId = target.index + 1;
                }
                arcSpacing = smallestLabelWidth - bx;
                if (!hasLeftArcs || spacingRowBreak < arcSpacing) {
                  spacingRowBreak = arcSpacing;
                }
                hasLeftArcs = true;
              } else {
                hasRightArcs = true;
              }
            });
            spanHeight += yAdjust || curlyHeight;
            if (spanHeight > chunkHeight) chunkHeight = spanHeight;
            hasAnnotations = true;
          }); // spans

          // positioning of the chunk
          chunk.right = chunkTo;
          var textWidth = sizes.texts.widths[chunk.text];
          chunkHeight += sizes.texts.height;
          var boxX = -Math.min(chunkFrom, 0);
          var boxWidth =
              Math.max(textWidth, chunkTo) -
              Math.min(0, chunkFrom);
          // if (hasLeftArcs) {
            // TODO change this with smallestLeftArc
            // var spacing = arcHorizontalSpacing - (current.x - lastArcBorder);
            // arc too small?
          if (spacing > 0) current.x += spacing;
          // }
          var rightBorderForArcs = hasRightArcs ? arcHorizontalSpacing : (hasInternalArcs ? arcSlant : 0);

          // open text highlights
          $.each(chunk.editedTextStart, function(textNo, textDesc) {
            textDesc[3] += current.x + boxX;
            openTextHighlights[textDesc[0]] = textDesc;
          });

          if (chunk.sentence) {
            while (sentenceNumber < chunk.sentence) {
              sentenceNumber++;
              row.arcs = svg.group(row.group, { 'class': 'arcs' });
              rows.push(row);
              row = new Row(svg);
              sentenceToggle = 1 - sentenceToggle;
              row.backgroundIndex = sentenceToggle;
              row.index = ++rowIndex;
            }
            sentenceToggle = 1 - sentenceToggle;
          }

          if (chunk.sentence ||
              current.x + boxWidth + rightBorderForArcs >= canvasWidth - 2 * margin.x) {
            // the chunk does not fit
            var lastX = current.x;
            row.arcs = svg.group(row.group, { 'class': 'arcs' });
            current.x = margin.x + sentNumMargin + rowPadding +
                (hasLeftArcs ? arcHorizontalSpacing : (hasInternalArcs ? arcSlant : 0));
            if (spacingRowBreak > 0) {
              current.x += spacingRowBreak;
              spacing = 0; // do not center intervening elements
            }

            // break the text highlights
            $.each(openTextHighlights, function(textId, textDesc) {
              if (textDesc[3] != lastX) {
                textEditedRows.push([row, textDesc[3], lastX + boxX]);
              }
              textDesc[3] = current.x;
            });

            // new row
            rows.push(row);

            svg.remove(chunk.group);
            row = new Row(svg);
            row.backgroundIndex = sentenceToggle;
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

          // close text highlights
          $.each(chunk.editedTextEnd, function(textNo, textDesc) {
            textDesc[3] += current.x + boxX;
            var startDesc = openTextHighlights[textDesc[0]];
            delete openTextHighlights[textDesc[0]];
            textEditedRows.push([row, startDesc[3], textDesc[3]]);
          });

          if (hasAnnotations) row.hasAnnotations = true;

          if (chunk.sentence) {
            row.sentence = ++sentenceNumber;
          }

          if (spacing > 0) {
            // if we added a gap, center the intervening elements
            spacing /= 2;
            var firstChunkInRow = row.chunks[row.chunks.length - 1];
            if (spacingChunkId < firstChunkInRow.index) {
              spacingChunkId = firstChunkInRow.index + 1;
            }
            for (var chunkIndex = spacingChunkId; chunkIndex < chunk.index; chunkIndex++) {
              var movedChunk = data.chunks[chunkIndex];
              translate(movedChunk, movedChunk.translation.x + spacing, 0);
              movedChunk.textX += spacing;
            }
          }

          row.chunks.push(chunk);
          chunk.row = row;

          translate(chunk, current.x + boxX, 0);
          chunk.textX = current.x + boxX;

          var spaceWidth = 0;
          var spaceLen = chunk.nextSpace && chunk.nextSpace.length || 0;
          for (var i = 0; i < spaceLen; i++) spaceWidth += spaceWidths[chunk.nextSpace[i]] || 0;
          current.x += spaceWidth + boxWidth;
        }); // chunks

        // finish the last row
        row.arcs = svg.group(row.group, { 'class': 'arcs' });
        rows.push(row);

Util.profileEnd('chunks');
Util.profileStart('arcsPrep');

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

Util.profileEnd('arcsPrep');
Util.profileStart('arcs');

        // add the arcs
        $.each(data.arcs, function(arcNo, arc) {
          roleClass = 'role_' + arc.type;

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

          var spanDesc = spanTypes[originSpan.type];
          // TODO: might make more sense to reformat this as dict instead
          // of searching through the list every type
          var arcDesc;
          if (spanDesc && spanDesc.arcs) {
              $.each(spanDesc.arcs, function(arcDescNo, arcDescIter) {
                      if (arcDescIter.type == arc.type) {
                          arcDesc = arcDescIter;
                      }
                  });            
          }
          // fall back on relation types in case origin span type is
          // undefined
          if (!arcDesc) {
            arcDesc = relationTypesHash[arc.type];
          }
          var color = arcDesc && arcDesc.color || spanTypes.ARC_DEFAULT.color || '#000000';
          var hashlessColor = color.replace('#', '');
          var dashArray = arcDesc && arcDesc.dashArray;
          var arrowHead = (arcDesc && arcDesc.arrowHead || spanTypes.ARC_DEFAULT.arrowHead || 'triangle,5') + ',' + hashlessColor;
          var arrowTail = (arcDesc && arcDesc.arrowTail || spanTypes.ARC_DEFAULT.arrowTail || 'triangle,5') + ',' + hashlessColor;

          var leftBox = rowBBox(left);
          var rightBox = rowBBox(right);
          var leftRow = left.chunk.row.index;
          var rightRow = right.chunk.row.index;

          if (!arrows[arrowHead]) {
            var arrow = makeArrow(defs, arrowHead);
            if (arrow) arrows[arrowHead] = arrow;
          }
          if (!arrows[arrowTail]) {
            var arrow = makeArrow(defs, arrowTail);
            if (arrow) arrows[arrowTail] = arrow;
          }

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

          // Adjust the height to align with pixels when rendered
          height += 0.5

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

            var originType = data.spans[arc.origin].type;
            var arcLabels = Util.getArcLabels(spanTypes, originType, arc.type);
            var labelText = Util.arcDisplayForm(spanTypes, originType, arc.type);
            if (abbrevsOn && !ufoCatcher && arcLabels) {
              var labelIdx = 1; // first abbreviation
              // strictly speaking 2*arcSlant would be needed to allow for
              // the full-width arcs to fit, but judged unabbreviated text
              // to be more important than the space for arcs.
              var maxLength = (to - from) - (arcSlant);
              while (sizes.arcs.widths[labelText] > maxLength &&
                     arcLabels[labelIdx]) {
                labelText = arcLabels[labelIdx];
                labelIdx++;
              }
            }

            var shadowGroup;
            if (arc.shadowClass || arc.edited) shadowGroup = svg.group(arcGroup);
            var options = {
              'fill': color,
              'data-arc-role': arc.type,
              'data-arc-origin': arc.origin,
              'data-arc-target': arc.target,
              'data-arc-id': arc.id,
              'data-arc-ed': arc.eventDescId,
            };
            var text = svg.text(arcGroup, (from + to) / 2, -height, labelText, options);
            var width = sizes.arcs.widths[labelText];
            var textBox = {
              x: (from + to - width) / 2,
              width: width,
              y: -height - sizes.arcs.height / 2,
              height: sizes.arcs.height,
            }
            if (arc.edited) {
              var editedRect = svg.rect(shadowGroup,
                  textBox.x - editedArcSize, textBox.y - editedArcSize,
                  textBox.width + 2 * editedArcSize, textBox.height + 2 * editedArcSize, {
                    // filter: 'url(#Gaussian_Blur)',
                    'class': "shadow_EditHighlight",
                    rx: editedArcSize,
                    ry: editedArcSize,
              });
              svg.other(editedRect, 'animate', {
                'data-type': arc.edited,
                attributeName: 'fill',
                values: highlightArcSequence,
                dur: highlightDuration,
                repeatCount: 'indefinite',
                begin: 'indefinite'
              });
            }
            if (arc.shadowClass) {
              svg.rect(shadowGroup,
                  textBox.x - shadowSize, textBox.y - shadowSize,
                  textBox.width + 2 * shadowSize, textBox.height + 2 * shadowSize, {
                    'class': 'blur shadow_' + arc.shadowClass,
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

            if (roundCoordinates) {
              // don't ask
              height = (height|0)+0.5;
            }

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
            var hashlessColor = color.replace('#', '');
            var arrowType = arrows[(leftToRight ?
                arcDesc && arcDesc.arrowTail || spanTypes.ARC_DEFAULT.arrowTail || 'none' :
                arcDesc && arcDesc.arrowHead || spanTypes.ARC_DEFAULT.arrowHead || 'triangle,5') + ',' + hashlessColor];
            svg.path(arcGroup, path, {
              markerEnd: arrowType && ('url(#' + arrowType + ')'),
              style: 'stroke: ' + color,
              'strokeDashArray': dashArray,
            });
            if (arc.edited) {
              svg.path(shadowGroup, path, {
                  'class': 'shadow_EditHighlight_arc',
                  strokeWidth: editedStroke,
                  'strokeDashArray': dashArray,
              });
              svg.other(editedRect, 'animate', {
                'data-type': arc.edited,
                attributeName: 'fill',
                values: highlightArcSequence,
                dur: highlightDuration,
                repeatCount: 'indefinite',
                begin: 'indefinite'
              });
            }
            if (arc.shadowClass) {
              svg.path(shadowGroup, path, {
                  'class': 'shadow_' + arc.shadowClass,
                  strokeWidth: shadowStroke,
                  'strokeDashArray': dashArray,
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
            var arrowType = arrows[(leftToRight ?
                arcDesc && arcDesc.arrowHead || spanTypes.ARC_DEFAULT.arrowHead || 'triangle,5' :
                arcDesc && arcDesc.arrowTail || spanTypes.ARC_DEFAULT.arrowTail || 'none') + ',' + hashlessColor];
            svg.path(arcGroup, path, {
                markerEnd: arrowType && ('url(#' + arrowType + ')'),
                style: 'stroke: ' + color,
                'strokeDashArray': dashArray,
            });
            if (arc.edited) {
              svg.path(shadowGroup, path, {
                  'class': 'shadow_EditHighlight_arc',
                  strokeWidth: editedStroke,
                  'strokeDashArray': dashArray,
              });
            }
            if (shadowGroup) {
              svg.path(shadowGroup, path, {
                  'class': 'shadow_' + arc.shadowClass,
                  strokeWidth: shadowStroke,
                  'strokeDashArray': dashArray,
              });
            }
          } // arc rows
        }); // arcs

Util.profileEnd('arcs');
Util.profileStart('rows');

        // position the rows
        var y = margin.y;
        var sentNumGroup = svg.group({'class': 'sentnum'});
        var currentSent;
        $.each(rows, function(rowId, row) {
          if (row.sentence) {
            currentSent = row.sentence;
          }
          var rowBox = row.group.getBBox();
          // Make it work on Firefox and Opera
          if (!rowBox || rowBox.height == -Infinity) {
            rowBox = { x: 0, y: 0, height: 0, width: 0 };
          }
          if (row.hasAnnotations) {
            rowBox.height = -rowBox.y+rowSpacing;
          }
          rowBox.height += rowPadding;
          svg.rect(backgroundGroup,
            0, y + sizes.texts.y + sizes.texts.height,
            canvasWidth, rowBox.height + sizes.texts.height + 1, {
            'class': 'background' +
                ($.inArray(currentSent, data.editedSent) != -1 ?
                 'Highlight' : row.backgroundIndex),
          });
          y += rowBox.height;
          y += sizes.texts.height;
          row.textY = y - rowPadding;
          if (row.sentence) {
            var text = svg.text(sentNumGroup, sentNumMargin - margin.x, y - rowPadding,
                '' + row.sentence, { 'data-sent': row.sentence });
            var sentComment = data.sentComment[row.sentence];
            if (sentComment) {
              var box = text.getBBox();
              svg.remove(text);
              shadowRect = svg.rect(sentNumGroup,
                  box.x - shadowSize, box.y - shadowSize,
                  box.width + 2 * shadowSize, box.height + 2 * shadowSize, {

                  'class': 'blur shadow_' + sentComment.type,
                  rx: shadowSize,
                  ry: shadowSize,
                  'data-sent': row.sentence,
              });
              var text = svg.text(sentNumGroup, sentNumMargin - margin.x, y - rowPadding,
                  '' + row.sentence, { 'data-sent': row.sentence });
            }
          }
          
          var rowY = y - rowPadding;
          if (roundCoordinates) {
            rowY = rowY|0;
          }
          translate(row, 0, rowY);
          y += margin.y;
        });
        y += margin.y;

Util.profileEnd('rows');
Util.profileStart('chunkFinish');

        // chunk index sort functions for overlapping span drawing
        // algorithm; first for left-to-right pass, sorting primarily
        // by start offset, second for right-to-left pass by end
        // offset. Secondary sort by span length in both cases.
        var currentChunk;
        var lrChunkComp = function(a,b) { 
          var ac = currentChunk.spans[a];
          var bc = currentChunk.spans[b]
          var startDiff = Util.cmp(ac.from, bc.from);
          return startDiff != 0 ? startDiff : Util.cmp(bc.to-bc.from, ac.to-ac.from);
        }
        var rlChunkComp = function(a,b) { 
          var ac = currentChunk.spans[a];
          var bc = currentChunk.spans[b]
          var endDiff = Util.cmp(bc.to, ac.to);
          return endDiff != 0 ? endDiff : Util.cmp(bc.to-bc.from, ac.to-ac.from);
        }

        $.each(data.chunks, function(chunkNo, chunk) {
          // context for sort
          currentChunk = chunk;

          // text rendering
          chunk.textElem = svg.text(textGroup, chunk.textX, chunk.row.textY, chunk.text,
            {
              'data-chunk-id': chunk.index
            });

          // chunk backgrounds
          if (chunk.spans.length) {
            var orderedIdx = [];
            for (var i=chunk.spans.length-1; i>=0; i--) {
              orderedIdx.push(i);
            }

            // Mark entity nesting height/depth (number of
            // nested/nesting entities). To account for crossing
            // brackets in a (mostly) reasonable way, determine
            // depth/height separately in a left-to-right traversal
            // and a right-to-left traversal.
            orderedIdx.sort(lrChunkComp);              
            
            var openSpans = [];
            for(var i=0; i<orderedIdx.length; i++) {
              var current = chunk.spans[orderedIdx[i]];
              current.nestingHeightLR = 0;
              current.nestingDepthLR = 0;
              var stillOpen = [];
              for(var o=0; o<openSpans.length; o++) {
                if(openSpans[o].to > current.from) {
                  stillOpen.push(openSpans[o]);
                  openSpans[o].nestingHeightLR++;
                }
              }
              openSpans = stillOpen;
              current.nestingDepthLR=openSpans.length;
              openSpans.push(current);
            }

            // re-sort for right-to-left traversal by end position
            orderedIdx.sort(rlChunkComp);

            openSpans = [];
            for(var i=0; i<orderedIdx.length; i++) {
              var current = chunk.spans[orderedIdx[i]];
              current.nestingHeightRL = 0;
              current.nestingDepthRL = 0;
              var stillOpen = [];
              for(var o=0; o<openSpans.length; o++) {
                if(openSpans[o].from < current.to) {
                  stillOpen.push(openSpans[o]);
                  openSpans[o].nestingHeightRL++;
                }
              }
              openSpans = stillOpen;
              current.nestingDepthRL=openSpans.length;
              openSpans.push(current);
            }

            // the effective depth and height are the max of those
            // for the left-to-right and right-to-left traversals.
            for(var i=0; i<orderedIdx.length; i++) {
              var c = chunk.spans[orderedIdx[i]];
              c.nestingHeight = c.nestingHeightLR > c.nestingHeightRL ? c.nestingHeightLR : c.nestingHeightRL;
              c.nestingDepth = c.nestingDepthLR > c.nestingDepthRL ? c.nestingDepthLR : c.nestingDepthRL;
            }              

            // Re-order by nesting height and draw in order
            orderedIdx.sort(function(a,b) { return Util.cmp(chunk.spans[b].nestingHeight, chunk.spans[a].nestingHeight) });

            for(var i=0; i<chunk.spans.length; i++) {
              var span=chunk.spans[orderedIdx[i]];
              var spanDesc = spanTypes[span.type];
              var bgColor = spanDesc && spanDesc.bgColor || spanTypes.SPAN_DEFAULT.bgColor || '#ffffff';

              // Tweak for nesting depth/height. Recognize just three
              // levels for now: normal, nested, and nesting, where
              // nested+nesting yields normal. (Currently testing
              // minor tweak: don't shrink for depth 1 as the nesting 
              // highlight will grow anyway [check nestingDepth > 1])
              var shrink = 0;
              if(span.nestingDepth > 1 && span.nestingHeight == 0) {
                  shrink = 1;
              } else if(span.nestingDepth == 0 && span.nestingHeight > 0) {
                  shrink = -1;
              }
              var yShrink = shrink * nestingAdjustYStepSize;
              var xShrink = shrink * nestingAdjustXStepSize;
              // bit lighter
              var lightBgColor = Util.adjustColorLightness(bgColor, 0.8);
              // store to have same mouseover highlight without recalc
              span.highlightPos = {
                  x: chunk.textX + span.curly.from - 1 + xShrink, 
                  y: chunk.row.textY + sizes.texts.y + 1 + yShrink, // XXX TODO: why +1??
                  w: span.curly.to - span.curly.from + 2 - 2*xShrink, 
                  h: sizes.spans.height + 2 - 2*yShrink,
              };
              svg.rect(highlightGroup,
                  span.highlightPos.x, span.highlightPos.y,
                  span.highlightPos.w, span.highlightPos.h,
                  { fill: lightBgColor, //opacity:1,
                    rx: highlightRounding.x,
                    ry: highlightRounding.y,
                  });
            }
          }
        });

        // draw the editedText
        $.each(textEditedRows, function(textRowNo, textRowDesc) { // row, from, to
          var textHighlight = svg.rect(highlightGroup,
              textRowDesc[1] - 2, textRowDesc[0].textY - sizes.spans.height,
              textRowDesc[2] - textRowDesc[1] + 4, sizes.spans.height + 4,
              { fill: 'yellow' } // TODO: put into css file, as default - turn into class
          );
          svg.other(textHighlight, 'animate', {
            attributeName: 'fill',
            values: highlightTextSequence,
            dur: highlightDuration,
            repeatCount: 'indefinite',
            begin: 'indefinite'
          });
        });


Util.profileEnd('chunkFinish');
Util.profileStart('finish');

        svg.path(sentNumGroup, svg.createPath().
          move(sentNumMargin, 0).
          line(sentNumMargin, y));
        // resize the SVG
        $svg.height(y);
        $svgDiv.height(y);

Util.profileEnd('finish');
Util.profileEnd('render');
Util.profileReport();


        drawing = false;
        if (redraw) {
          redraw = false;
          renderDataReal();
        }
        $svg.find('animate').each(function() {
          this.beginElement();
        });
        dispatcher.post('doneRendering', [coll, doc, args]);
      };

      var renderErrors = {
        unableToReadTextFile: true,
        annotationFileNotFound: true,
        isDirectoryError: true
      };
      var renderData = function(_data) {
        Util.profileEnd('invoke getDocument');
        if (_data && _data.exception) {
          if (renderErrors[_data.exception]) {
            dispatcher.post('renderError:' + _data.exception, [_data]);
          } else {
            dispatcher.post('unknownError', [_data.exception]);
          }
        } else {
          dispatcher.post('startedRendering', [coll, doc, args]);
          dispatcher.post('spin');
          setTimeout(function() {
              renderDataReal(_data);
              dispatcher.post('unspin');
          }, 0);
        }
      };

      var renderDocument = function() {
        Util.profileStart('invoke getDocument');
        dispatcher.post('ajax', [{
            action: 'getDocument',
            collection: coll,
            'document': doc,
          }, 'renderData', {
            collection: coll,
            'document': doc
          }]);
      };

      var triggerRender = function() {
        if (svg && isRenderRequested && isCollectionLoaded && areFontsLoaded) {
          isRenderRequested = false;
          if (doc.length) {

Util.profileClear();
Util.profileStart('before render');

            renderDocument();
          } else {
            dispatcher.post(0, 'renderError:noFileSpecified');
          }
        }
      };

      var collectionChanged = function() {
        isCollectionLoaded = false;
      };

      var gotCurrent = function(_coll, _doc, _args, reloadData) {
        coll = _coll;
        doc  = _doc;
        args = _args;
        if (reloadData) {
          isRenderRequested = true;
          triggerRender();
        }
      };


      // event handlers

      var highlight, highlightArcs, highlightSpans, commentId;

      var onMouseOver = function(evt) {
        var target = $(evt.target);
        var id;
        if (id = target.attr('data-span-id')) {
          commentId = id;
          var span = data.spans[id];
          dispatcher.post('displaySpanComment', [
              evt, target, id, span.type, span.attributeText,
              data.text.substring(span.from, span.to),
              span.comment && span.comment.text,
              span.comment && span.comment.type]);

          var spanDesc = spanTypes[span.type];
          var bgColor = spanDesc && spanDesc.bgColor || spanTypes.SPAN_DEFAULT.bgColor || '#ffffff';
          highlight = svg.rect(highlightGroup,
                               span.highlightPos.x, span.highlightPos.y,
                               span.highlightPos.w, span.highlightPos.h,
                               { 'fill': bgColor, opacity:0.75,
                                 rx: highlightRounding.x,
                                 ry: highlightRounding.y,
                               });

          if (that.arcDragOrigin) {
            target.parent().addClass('highlight');
          } else {
            highlightArcs = $svg.
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
            highlightSpans = $svg.
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
          // NOTE: no commentText, commentType for now
          var arcEventDescId = target.attr('data-arc-ed');
          var commentText = '';
          var commentType = '';
          var arcId;
          if (arcEventDescId) {
            var eventDesc = data.eventDescs[arcEventDescId];
            var comment = eventDesc.comment;
            if (comment) {
              commentText = comment.text;
              commentType = comment.type;
              if (commentText == '' && commentType) {
                  // default to type if missing text
                  commentText = commentType;
              }
            }
            if (eventDesc.relation) {
              // among arcs, only ones corresponding to relations have "independent" IDs
              arcId = arcEventDescId;
            }
          }
          dispatcher.post('displayArcComment', [
              evt, target, symmetric, arcId,
              originSpanId, role, targetSpanId,
              commentText, commentType]);
          highlightArcs = $svg.
              find('g[data-from="' + originSpanId + '"][data-to="' + targetSpanId + '"]').
              addClass('highlight');
          highlightSpans = $($svg).
              find('rect[data-span-id="' + originSpanId + '"], rect[data-span-id="' + targetSpanId + '"]').
              parent().
              addClass('highlight');
        } else if (id = target.attr('data-sent')) {
          var comment = data.sentComment[id];
          if (comment) {
            dispatcher.post('displaySentComment', [evt, target, comment.text, comment.type]);
          }
        }
      };

      var onMouseOut = function(evt) {
        var target = $(evt.target);
        dispatcher.post('hideComment');
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

      var setAbbrevs = function(_abbrevsOn) {
        abbrevsOn = _abbrevsOn;
      }

      $svgDiv = $($svgDiv).hide();

      // register event listeners
      var registerHandlers = function(element, events) {
        $.each(events, function(eventNo, eventName) {
            element.bind(eventName,
              function(evt) {
                dispatcher.post(eventName, [evt], 'all');
              }
            );
        });
      };
      registerHandlers($svgDiv, [
          'mouseover', 'mouseout', 'mousemove',
          'mouseup', 'mousedown',
          'dragstart',
          'dblclick', 'click'
      ]);
      registerHandlers($(document), [
          'keydown', 'keypress'
      ]);
      registerHandlers($(window), [
          'resize'
      ]);

      // create the svg wrapper
      $svgDiv.svg({
          onLoad: function(_svg) {
              that.svg = svg = _svg;
              $svg = $(svg._svg);

              /* XXX HACK REMOVED - not efficient?

              // XXX HACK to allow off-DOM SVG element creation
              // we need to replace the jQuery SVG's _makeNode function
              // with a modified one.
              // Be aware of potential breakage upon jQuery SVG upgrade.
              svg._makeNode = function(parent, name, settings) {
                  // COMMENTED OUT: parent = parent || this._svg;
                  var node = this._svg.ownerDocument.createElementNS($.svg.svgNS, name);
                  for (var name in settings) {
                    var value = settings[name];
                    if (value != null && value != null && 
                        (typeof value != 'string' || value != '')) {
                      node.setAttribute($.svg._attrNames[name] || name, value);
                    }
                  }
                  // ADDED IN:
                  if (parent)
                    parent.appendChild(node);
                  return node;
                };
              */

              triggerRender();
          }
      });

      var loadSpanTypes = function(types) {
        $.each(types, function(typeNo, type) {
          if (type) {
            spanTypes[type.type] = type;
            var children = type.children;
            if (children && children.length) {
              loadSpanTypes(children);
            }
          }
        });
      }

      var collectionLoaded = function(response) {
        if (!response.exception) {
          attributeTypes = {};
          $.each(response.attribute_types, function(aTypeNo, aType) {
            attributeTypes[aType.type] = aType;
            // count the values; if only one, it's a boolean attribute
            var values = [];
            for (var i in aType.values) {
              if (aType.values.hasOwnProperty(i)) {
                values.push(i);
              }
            }
            if (values.length == 1) {
              aType.bool = values[0];
            }
          });

          spanTypes = {};
          loadSpanTypes(response.entity_types);
          loadSpanTypes(response.event_types);
          loadSpanTypes(response.unconfigured_types);
          relationTypesHash = {};
          $.each(response.relation_types, function(relTypeNo, relType) {
            relationTypesHash[relType.type] = relType;
          });

          dispatcher.post('spanAndAttributeTypesLoaded', [spanTypes, attributeTypes]);

          isCollectionLoaded = true;
          triggerRender();
        } else {
          // exception on collection load; allow visualizer_ui
          // collectionLoaded to handle this
        }
      };

      var fontTestString = 'abbcccddddeeeeeffffffggggggghhhhhhhhiiiiiiiiijjjjjjjjjjkkkkkkkkkkkllllllllllllmmmmmmmmmmmmmnnnnnnnnnnnnnnoooooooooooooooppppppppppppppppqqqqqqqqqqqqqqqqqrrrrrrrrrrrrrrrrrrsssssssssssssssssssttttttttttttttttttttuuuuuuuuuuuuuuuuuuuuuvvvvvvvvvvvvvvvvvvvvvvwwwwwwwwwwwwwwwwwwwwwwwxxxxxxxxxxxxxxxxxxxxxxxxyyyyyyyyyyyyyyyyyyyyyyyyyzzzzzzzzzzzzzzzzzzzzzzzzzz';
      var waitUntilFontsLoaded = function(fonts) {
        var interval = 50;
        var maxTime = 1000; // max wait 1s for fonts
        var $fontsTester = $('<div style="font-size: 72px; width: 1px"/>');
        $('body').append($fontsTester);
        var $serifDiv = $('<div style="font-family: serif"/>').text(fontTestString);
        $.each(fonts, function(fontNo, font) {
          var $newDiv = $('<div style="font-family: ' + font + '; overflow: scroll"/>').text(fontTestString);
          $fontsTester.append($newDiv, $serifDiv);
        });
        
        var waitUntilFontsLoadedInner = function(fonts, remainingTime, interval) {
          var allLoaded = true;
          $fontsTester.each(function() {
            var newWidth = this.scrollWidth;
            var serifWidth = $serifDiv[0].scrollWidth;
            if (newWidth == serifWidth) {
              allLoaded = false;
              return false;
            }
          });
          allLoaded = false;
          if (allLoaded || remainingTime <= 0) {
            areFontsLoaded = true;
            triggerRender();
          } else {
            setTimeout(function() { waitUntilFontsLoadedInner(fonts, remainingTime - interval, interval); }, interval);
          }
        };

        waitUntilFontsLoadedInner(fonts, maxTime, interval);
        $fontsTester.remove();
      }

      waitUntilFontsLoaded([
        'Astloch',
        'PT Sans Caption'
      ]);




      dispatcher.
          on('collectionChanged', collectionChanged).
          on('collectionLoaded', collectionLoaded).
          on('renderData', renderData).
          on('resetData', resetData).
          on('abbrevs', setAbbrevs).
          on('current', gotCurrent).
          on('mouseover', onMouseOver).
          on('mouseout', onMouseOut);
    };

    return Visualizer;
})(jQuery, window);
