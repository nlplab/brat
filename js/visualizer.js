var Visualizer = (function($, window, undefined) {
    var Visualizer = function(dispatcher, svg) {
      var visualizer = this;

      var data = null;
      var dir;
      var doc;
      var abbrevs;
      var isRenderRequested;

      var infoPrioLevels = ['Unconfirmed', 'Incomplete', 'Warning', 'Error'];

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

      var infoPriority = function(infoClass) {
        if (infoClass === undefined) return -1;
        var len = infoPrioLevels.length;
        for (var i = 0; i < len; i++) {
          if (infoClass.indexOf(infoPrioLevels[i]) != -1) return i;
        }
        return 0;
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
            dispatcher.post('messages', [['<strong>ERROR</strong><br/>Event ' + mod[2] + ' (referenced from modification ' + mod[0] + ') does not occur in document ' + data.document + '<br/>(please correct the source data)', 'error', 5]]);
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
            dispatcher.post('messages', [['<strong>ERROR</strong><br/>Trigger for event "' + eventDesc.id + '" not found in ' + data.document + '<br/>(please correct the source data)', 'error', 5]]);
            throw "BadDocumentError";
          }
          var here = origin.chunk.index;
          $.each(eventDesc.roles, function(roleNo, role) {
            var target = data.spans[role.targetId];
            if (!target) {
              dispatcher/post('messages', [['<strong>ERROR</strong><br/>"' + role.targetId + '" (referenced from "' + eventDesc.id + '") not found in ' + data.document + '<br/>(please correct the source data)', 'error', 5]]);
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
              editedSent = edited[1];
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
                        arc.edited = true;
                      }
                      return; // next equiv
                    }
                  }
                }
              });
            } else {
              editedSent = null;
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

        console.log(data);
      };

      var renderData = function(_data) {
        if (_data) {
          setData(_data);
        }
        // TODO render
      };

      var renderDocument = function() {
        dispatcher.post('ajax', [{
            directory: dir,
            'document': doc,
          }, 'renderData']);
      };

      var triggerRender = function() {
        if (isRenderRequested && isDirLoaded) {
          isRenderRequested = false;
          renderDocument();
        }
      };
      
      var dirChanged = function() {
        isDirLoaded = false;
      };

      var dirLoaded = function(response) {
        abbrevs = response.abbrevs;
        isDirLoaded = true;
        triggerRender();
      };

      var gotCurrent = function(_dir, _doc, _args) {
        dir = _dir;
        doc = _doc;
        args = _args;
        isRenderRequested = true;
        triggerRender();
      };

      dispatcher.
          on('dirChanged', dirChanged).
          on('dirLoaded', dirLoaded).
          on('renderData', renderData).
          on('current', gotCurrent);
    };

    return Visualizer;
})(jQuery, window);
