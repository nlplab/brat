// vim:set ft=javascript ts=2 sw=2 sts=2 cindent:

var Visualizer = (function($, window, undefined) {
    var DocumentData = function(text) {
      this.text = text;
      this.chunks = [];
      this.spans = {};
      this.eventDescs = {};
      this.sentComment = {};
      this.arcs = [];
      this.arcById = {};
      this.markedSent = {};
      this.spanAnnTexts = {};
      this.towers = {};
      // this.sizes = {};
    };

    var Fragment = function(id, span, from, to) {
      this.id = id;
      this.span = span;
      this.from = from;
      this.to = to;
      // this.towerId = undefined;
      // this.drawOrder = undefined;
    };

    var Span = function(id, type, offsets, generalType) {
      this.id = id;
      this.type = type;
      this.totalDist = 0;
      this.numArcs = 0;
      this.generalType = generalType;
      this.headFragment = null;
      this.unsegmentedOffsets = offsets;
      this.offsets = [];
      this.segmentedOffsetsMap = {};
      // this.unsegmentedOffsets = undefined;
      // this.from = undefined;
      // this.to = undefined;
      // this.wholeFrom = undefined;
      // this.wholeTo = undefined;
      // this.headFragment = undefined;
      // this.chunk = undefined;
      // this.marked = undefined;
      // this.avgDist = undefined;
      // this.curly = undefined;
      // this.comment = undefined; // { type: undefined, text: undefined };
      // this.annotatorNotes = undefined;
      // this.drawCurly = undefined;
      // this.glyphedLabelText = undefined;
      // this.group = undefined;
      // this.height = undefined;
      // this.highlightPos = undefined;
      // this.indexNumber = undefined;
      // this.labelText = undefined;
      // this.nestingDepth = undefined;
      // this.nestingDepthLR = undefined;
      // this.nestingDepthRL = undefined;
      // this.nestingHeight = undefined;
      // this.nestingHeightLR = undefined;
      // this.nestingHeightRL = undefined;
      // this.rect = undefined;
      // this.rectBox = undefined;
      // this.refedIndexSum = undefined;
      // this.right = undefined;
      // this.totaldist = undefined;
      // this.width = undefined;
      this.initContainers();
    };

    Span.prototype.initContainers = function(offsets) {
      this.incoming = [];
      this.outgoing = [];
      this.attributes = {};
      this.attributeText = [];
      this.attributeCues = {};
      this.attributeCueFor = {};
      this.attributeMerge = {}; // for box, cross, etc. that are span-global
      this.fragments = [];
      this.normalizations = [];
    };

    Span.prototype.splitMultilineOffsets = function(text) {
      this.segmentedOffsetsMap = {};

      for (var fi = 0, nfi = 0; fi < this.unsegmentedOffsets.length; fi++) {
        var begin = this.unsegmentedOffsets[fi][0];
        var end = this.unsegmentedOffsets[fi][1];

        for (var ti = begin; ti < end; ti++) {
          var c = text.charAt(ti);
          if (c == '\n' || c == '\r') {
            if (begin !== null) {
              this.offsets.push([begin, ti])
              this.segmentedOffsetsMap[nfi++] = fi;
              begin = null;
            }
          }
          else if (begin === null) {
            begin = ti;
          }
        }

        if (begin !== null) {
          this.offsets.push([begin, end]);
          this.segmentedOffsetsMap[nfi++] = fi;
        }
      }
    };

    Span.prototype.copy = function(id) {
      var span = $.extend(new Span(), this); // clone
      span.id = id;
      // protect from shallow copy
      span.initContainers();
      span.unsegmentedOffsets = this.unsegmentedOffsets.slice();
      // read-only; shallow copy is fine
      span.offsets = this.offsets;
      span.segmentedOffsetsMap = this.segmentedOffsetsMap;
      return span;
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
      // this.leftSpans = undefined;
      // this.rightSpans = undefined;
      // this.annotatorNotes = undefined;
    };

    var Chunk = function(index, text, from, to, space, spans) {
      this.index = index;
      this.text = text;
      this.from = from;
      this.to = to;
      this.space = space;
      this.fragments = [];
      // this.sentence = undefined;
      // this.group = undefined;
      // this.highlightGroup = undefined;
      // this.markedTextStart = undefined;
      // this.markedTextEnd = undefined;
      // this.nextSpace = undefined;
      // this.right = undefined;
      // this.row = undefined;
      // this.textX = undefined;
      // this.translation = undefined;
    }

    var Arc = function(eventDesc, role, dist, eventNo) {
      this.origin = eventDesc.id;
      this.target = role.targetId;
      this.dist = dist;
      this.type = role.type;
      this.shadowClass = eventDesc.shadowClass;
      this.jumpHeight = 0;
      if (eventDesc.equiv) {
        this.equiv = true;
        this.eventDescId = eventNo;
        eventDesc.equivArc = this;
      } else if (eventDesc.relation) {
        this.relation = true;
        this.eventDescId = eventNo;
      }
      // this.marked = undefined;
    };

    var Row = function(svg) {
      this.group = svg.group();
      this.background = svg.group(this.group);
      this.chunks = [];
      this.hasAnnotations = false;
      this.maxArcHeight = 0;
      this.maxSpanHeight = 0;
    };

    var Measurements = function(widths, height, y) {
      this.widths = widths;
      this.height = height;
      this.y = y;
    };

    // A naive whitespace tokeniser
    var tokenise = function(text) {
      var tokenOffsets = [];
      var tokenStart = null;
      var lastCharPos = null;

      for (var i = 0; i < text.length; i++) {
        var c = text.charAt(i);
        // Have we found the start of a token?
        if (tokenStart == null && !/\s/.test(c)) {
          tokenStart = i;
          lastCharPos = i;
        // Have we found the end of a token?
        } else if (/\s/.test(c) && tokenStart != null) {
          tokenOffsets.push([tokenStart, i]);
          tokenStart = null;
        // Is it a non-whitespace character?
        } else if (!/\s/.test(c)) {
          lastCharPos = i;
        }
      }
      // Do we have a trailing token?
      if (tokenStart != null) {
        tokenOffsets.push([tokenStart, lastCharPos + 1]);
      }

      return tokenOffsets;
    };

    // A naive newline sentence splitter
    var sentenceSplit = function(text) {
      var sentenceOffsets = [];
      var sentStart = null;
      var lastCharPos = null;

      for (var i = 0; i < text.length; i++) {
        var c = text[i];
        // Have we found the start of a sentence?
        if (sentStart == null && !/\s/.test(c)) {
          sentStart = i;
          lastCharPos = i;
        // Have we found the end of a sentence?
        } else if (c == '\n' && sentStart != null) {
          sentenceOffsets.push([sentStart, i]);
          sentStart = null;
        // Is it a non-whitespace character?
        } else if (!/\s/.test(c)) {
          lastCharPos = i;
        }
      }
      // Do we have a trailing sentence without a closing newline?
      if (sentStart != null) {
        sentenceOffsets.push([sentStart, lastCharPos + 1]);
      }

      return sentenceOffsets;
    };

    // Sets default values for a wide range of optional attributes
    var setSourceDataDefaults = function(sourceData) {
      // The following are empty lists if not set
      $.each([
          'attributes',
          'comments',
          'entities',
          'equivs',
          'events',
          'modifications',
          'normalizations',
          'relations',
          'triggers',
          ], function(attrNo, attr) {
        if (sourceData[attr] === undefined) {
          sourceData[attr] = [];
        }
      });

      // If we lack sentence offsets we fall back on naive sentence splitting
      if (sourceData.sentence_offsets === undefined) {
        sourceData.sentence_offsets = sentenceSplit(sourceData.text);
      }
      // Similarily we fall back on whitespace tokenisation
      if (sourceData.token_offsets === undefined) {
        sourceData.token_offsets = tokenise(sourceData.text);
      }
    };

    // Set default values for a variety of collection attributes
    var setCollectionDefaults = function(collectionData) {
      // The following are empty lists if not set
      $.each([
          'entity_attribute_types',
          'entity_types',
          'event_attribute_types',
          'event_types',
          'relation_attribute_types',
          'relation_types',
          'unconfigured_types',
          ], function(attrNo, attr) {
        if (collectionData[attr] === undefined) {
          collectionData[attr] = [];
        }
      });
    };

    var Visualizer = function(dispatcher, svgId, webFontURLs) {
      var $svgDiv = $('#' + svgId);
      if (!$svgDiv.length) {
        throw Error('Could not find container with id="' + svgId + '"');
      }
      var that = this;

      // OPTIONS
      var roundCoordinates = true; // try to have exact pixel offsets
      var boxTextMargin = { x: 0, y: 1.5 }; // effect is inverse of "margin" for some reason
      var highlightRounding = { x: 3, y:3 }; // rx, ry for highlight boxes
      var spaceWidths = {
        ' ': 4,
        '\u00a0': 4,
        '\u200b': 0,
        '\u3000': 8,
        '\t': 12,
        '\n': 4
      };
      var coloredCurlies = true; // color curlies by box BG
      var arcSlant = 15; //10;
      var minArcSlant = 8;
      var arcHorizontalSpacing = 10; // min space boxes with connecting arc
      var rowSpacing = -5;          // for some funny reason approx. -10 gives "tight" packing.
      var sentNumMargin = 31;
      var smoothArcCurves = true;   // whether to use curves (vs lines) in arcs
      var smoothArcSteepness = 0.5; // steepness of smooth curves (control point)
      var reverseArcControlx = 5;   // control point distance for "UFO catchers"

      // "shadow" effect settings (note, error, incompelete)
      var rectShadowSize = 3;
      var rectShadowRounding = 2.5;
      var arcLabelShadowSize = 1;
      var arcLabelShadowRounding = 5;
      var shadowStroke = 2.5; // TODO XXX: this doesn't affect anything..?

      // "marked" effect settings (edited, focus, match)
      var markedSpanSize = 6;
      var markedArcSize = 2;
      var markedArcStroke = 7; // TODO XXX: this doesn't seem to do anything..?

      var rowPadding = 2;
      var nestingAdjustYStepSize = 2; // size of height adjust for nested/nesting spans
      var nestingAdjustXStepSize = 1; // size of height adjust for nested/nesting spans

      var highlightSequence = '#FF9632;#FFCC00;#FF9632'; // yellow - deep orange
      //var highlightSequence = '#FFFC69;#FFCC00;#FFFC69'; // a bit toned town
      var highlightSpanSequence = highlightSequence;
      var highlightArcSequence =  highlightSequence;
      var highlightTextSequence = highlightSequence;
      var highlightDuration = '2s';
      // different sequence for "mere" matches (as opposed to "focus" and
      // "edited" highlights)
      var highlightMatchSequence = '#FFFF00'; // plain yellow

      var fragmentConnectorDashArray = '1,3,3,3';
      var fragmentConnectorColor = '#000000';

      // END OPTIONS


      var svg;
      var $svg;
      var data = null;
      var sourceData = null;
      var requestedData = null;
      var coll, doc, args;
      var relationTypesHash;
      var isRenderRequested;
      var isCollectionLoaded = false;
      var entityAttributeTypes = null;
      var eventAttributeTypes = null;
      var spanTypes = null;
      var highlightGroup;
      var collapseArcs = false;
      var hideMidArcs = false;
      var rtlmode = false;
      var collapseArcSpace = false;
      var pagingOffset = 0;

      // var commentPrioLevels = ['Unconfirmed', 'Incomplete', 'Warning', 'Error', 'AnnotatorNotes'];
      // XXX Might need to be tweaked - inserted diff levels
      var commentPrioLevels = [
        'Unconfirmed', 'Incomplete', 'Warning', 'Error', 'AnnotatorNotes',
        'AddedAnnotation', 'MissingAnnotation', 'ChangedAnnotation'];

      this.arcDragOrigin = null; // TODO

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
        data = null;
        sourceData = null;
        svg.clear();
        $svgDiv.hide();
      };

      var setMarked = function(markedType) {
        $.each(args[markedType] || [], function(markedNo, marked) {
          if (marked[0] == 'sent') {
            data.markedSent[marked[1]] = true;
          } else if (marked[0] == 'equiv') { // [equiv, Equiv, T1]
            $.each(sourceData.equivs, function(equivNo, equiv) {
              if (equiv[1] == marked[1]) {
                var len = equiv.length;
                for (var i = 2; i < len; i++) {
                  if (equiv[i] == marked[2]) {
                    // found it
                    len -= 3;
                    for (var i = 1; i <= len; i++) {
                      var arc = data.eventDescs[equiv[0] + "*" + i].equivArc;
                      arc.marked = markedType;
                    }
                    return; // next equiv
                  }
                }
              }
            });
          } else if (marked.length == 2) {
            markedText.push([parseInt(marked[0], 10), parseInt(marked[1], 10), markedType]);
          } else {
            var span = data.spans[marked[0]];
            if (span) {
              if (marked.length == 3) { // arc
                $.each(span.outgoing, function(arcNo, arc) {
                  if (arc.target == marked[2] && arc.type == marked[1]) {
                    arc.marked = markedType;
                  }
                });
              } else { // span
                span.marked = markedType;
              }
            } else {
              var eventDesc = data.eventDescs[marked[0]];
              if (eventDesc) { // relation
                var relArc = eventDesc.roles[0];
                $.each(data.spans[eventDesc.triggerId].outgoing, function(arcNo, arc) {
                  if (arc.target == relArc.targetId && arc.type == relArc.type) {
                    arc.marked = markedType;
                  }
                });
              } else { // try for trigger
                $.each(data.eventDescs, function(eventDescNo, eventDesc) {
                  if (eventDesc.triggerId == marked[0]) {
                    data.spans[eventDesc.id].marked = markedType;
                  }
                });
              }
            }
          }
        });
      };

      var findArcHeight = function(fromIndex, toIndex, fragmentHeights) {
        var height = 0;
        for (var i = fromIndex; i <= toIndex; i++) {
          if (fragmentHeights[i] > height) height = fragmentHeights[i];
        }
        height += Configuration.visual.arcSpacing;
        return height;
      }

      var adjustFragmentHeights = function(fromIndex, toIndex, fragmentHeights, height) {
        for (var i = fromIndex; i <= toIndex; i++) {
          if (fragmentHeights[i] < height) fragmentHeights[i] = height;
        }
      }

      var fragmentComparator = function(a, b) {
        var tmp;
        var aSpan = a.span;
        var bSpan = b.span;

        // spans with more fragments go first
        tmp = aSpan.fragments.length - bSpan.fragments.length;
        if (tmp) {
          return tmp < 0 ? 1 : -1;
        }

        // longer arc distances go last
        tmp = aSpan.avgDist - bSpan.avgDist;
        if (tmp) {
          return tmp < 0 ? -1 : 1;
        }
        // spans with more arcs go last
        tmp = aSpan.numArcs - bSpan.numArcs;
        if (tmp) {
          return tmp < 0 ? -1 : 1;
        }
        // compare the span widths,
        // put wider on bottom so they don't mess with arcs, or shorter
        // on bottom if there are no arcs.
        var ad = a.to - a.from;
        var bd = b.to - b.from;
        tmp = ad - bd;
        if (aSpan.numArcs == 0 && bSpan.numArcs == 0) {
          tmp = -tmp;
        }
        if (tmp) {
          return tmp < 0 ? 1 : -1;
        }
        tmp = aSpan.refedIndexSum - bSpan.refedIndexSum;
        if (tmp) {
          return tmp < 0 ? -1 : 1;
        }
        // if no other criterion is found, sort by type to maintain
        // consistency
        // TODO: isn't there a cmp() in JS?
        if (aSpan.type < bSpan.type) {
          return -1;
        } else if (aSpan.type > bSpan.type) {
          return 1;
        }

        return 0;
      };


      var outOfPage = function(sentenceNo) {
        if (!Configuration.pagingSize) return 0;
        if (sentenceNo < pagingOffset) return -1;
        if (sentenceNo >= pagingOffset + Configuration.pagingSize) return 1;
        return 0;
      };

      var setData = function(_sourceData) {
        if (!args) args = {};
        sourceData = _sourceData;
        dispatcher.post('newSourceData', [sourceData]);
        data = new DocumentData(sourceData.text);

        // collect annotation data
        $.each(sourceData.entities, function(entityNo, entity) {
          // offsets given as array of (start, end) pairs
          var span =
              //      (id,        type,      offsets,   generalType)
              new Span(entity[0], entity[1], entity[2], 'entity');
          span.splitMultilineOffsets(data.text);
          data.spans[entity[0]] = span;
        });
        var triggerHash = {};
        $.each(sourceData.triggers, function(triggerNo, trigger) {
                       //       (id,         type,       offsets,    generalType)
          var triggerSpan = new Span(trigger[0], trigger[1], trigger[2], 'trigger');
          triggerSpan.splitMultilineOffsets(data.text);
          triggerHash[trigger[0]] = [triggerSpan, []]; // triggerSpan, eventlist
        });
        $.each(sourceData.events, function(eventNo, eventRow) {
          var eventDesc = data.eventDescs[eventRow[0]] =
              //           (id,          triggerId,   roles,        klass)
              new EventDesc(eventRow[0], eventRow[1], eventRow[2]);
          var trigger = triggerHash[eventDesc.triggerId];
          var span = trigger[0].copy(eventDesc.id);
          trigger[1].push(span);
          data.spans[eventDesc.id] = span;
        });

        // XXX modifications: delete later
        $.each(sourceData.modifications, function(modNo, mod) {
          // mod: [id, spanId, modification]
          if (!data.spans[mod[2]]) {
            dispatcher.post('messages', [[['<strong>ERROR</strong><br/>Event ' + mod[2] + ' (referenced from modification ' + mod[0] + ') does not occur in document ' + data.document + '<br/>(please correct the source data)', 'error', 5]]]);
            return;
          }
          data.spans[mod[2]][mod[1]] = true;
        });

        var midpointComparator = function(a, b) {
          var tmp = a.from + a.to - b.from - b.to;
          if (!tmp) return 0;
          return tmp < 0 ? -1 : 1;
        };
        // split spans into span fragments (for discontinuous spans)
        $.each(data.spans, function(spanNo, span) {
          $.each(span.offsets, function(offsetsNo, offsets) {
            var from = parseInt(offsets[0], 10);
            var to = parseInt(offsets[1], 10);
            var fragment = new Fragment(offsetsNo, span, from, to);
            span.fragments.push(fragment);
          });
          // ensure ascending order
          span.fragments.sort(midpointComparator);
          span.wholeFrom = span.fragments[0].from;
          span.wholeTo = span.fragments[span.fragments.length - 1].to;
        });

        // prepare span boundaries for token containment testing
        var sortedFragments = [];
        $.each(data.spans, function(spanNo, span) {
          $.each(span.fragments, function(fragmentNo, fragment) {
            sortedFragments.push(fragment);
          });
        });
        // sort fragments by beginning, then by end
        sortedFragments.sort(function(a, b) {
          var x = a.from;
          var y = b.from;
          if (x == y) {
            x = a.to;
            y = b.to;
          }
          return ((x < y) ? -1 : ((x > y) ? 1 : 0));
        });
        var currentFragmentId = 0;
        var startFragmentId = 0;
        var numFragments = sortedFragments.length;
        var lastTo = 0;
        var firstFrom = null;
        var chunkNo = 0;
        var space;
        var chunk = null;
        // token containment testing (chunk recognition)
        $.each(sourceData.token_offsets, function() {
          var from = this[0];
          var to = this[1];
          if (firstFrom === null) firstFrom = from;

          // Replaced for speedup; TODO check correctness
          // inSpan = false;
          // $.each(data.spans, function(spanNo, span) {
          //   if (span.from < to && to < span.to) {
          //     // it does; no word break
          //     inSpan = true;
          //     return false;
          //   }
          // });

          // Is the token end inside a span?
          if (startFragmentId && to > sortedFragments[startFragmentId - 1].to) {
            while (startFragmentId < numFragments && to > sortedFragments[startFragmentId].from) {
              startFragmentId++;
            }
          }
          currentFragmentId = startFragmentId;
          while (currentFragmentId < numFragments && to >= sortedFragments[currentFragmentId].to) {
            currentFragmentId++;
          }
          // if yes, the next token is in the same chunk
          if (currentFragmentId < numFragments && to > sortedFragments[currentFragmentId].from) {
            return;
          }

          // otherwise, create the chunk found so far
          space = data.text.substring(lastTo, firstFrom);
          var text = data.text.substring(firstFrom, to);
          if (chunk) chunk.nextSpace = space;
          //               (index,     text, from,      to, space) {
          chunk = new Chunk(chunkNo++, text, firstFrom, to, space);
          chunk.lastSpace = space;
          data.chunks.push(chunk);
          lastTo = to;
          firstFrom = null;
        });
        var numChunks = chunkNo;

        // find sentence boundaries in relation to chunks
        chunkNo = 0;
        var sentenceNo = 0;
        var pastFirst = false;
        var pos = outOfPage(sentenceNo);
        $.each(sourceData.sentence_offsets, function() {
          var from = this[0];
          if (chunkNo >= numChunks) return false;
          if (data.chunks[chunkNo].from > from) return;
          var chunk;
          while (chunkNo < numChunks && (chunk = data.chunks[chunkNo]).from < from) {
            chunk.outOfPage = pos;
            chunkNo++;
          }
          chunkNo++;
          if (pastFirst && from <= chunk.from) {
            var numNL = chunk.space.split("\n").length - 1;
            if (!numNL) numNL = 1;
            sentenceNo += numNL;
            pos = outOfPage(sentenceNo);
            chunk.sentence = sentenceNo;
          } else {
            pastFirst = true;
          }
          chunk.outOfPage = pos;
        });
        while (chunkNo < numChunks) {
          data.chunks[chunkNo++].outOfPage = Configuration.pagingSize ? pos : 0;
        }

        // assign fragments to appropriate chunks
        var currentChunkId = 0;
        var chunk;
        $.each(sortedFragments, function(fragmentId, fragment) {
          while (fragment.to > (chunk = data.chunks[currentChunkId]).to) currentChunkId++;
          chunk.fragments.push(fragment);
          fragment.text = chunk.text.substring(fragment.from - chunk.from, fragment.to - chunk.from);
          fragment.chunk = chunk;
          var pos = chunk.outOfPage;
          if (pos == 0) {
            if (!fragment.span.firstFragment) fragment.span.firstFragment = fragment;
            fragment.span.lastFragment = fragment;
          }
        });

        $.each(data.spans, function(spanNo, span) {
          if (!span.firstFragment) {
            span.firstFragment = span.lastFragment = span.fragments[0];
          }
          span.headFragment = span.lastFragment; // TODO configurable?
        });

        var spanComparator = function(a, b) {
          var aSpan = data.spans[a];
          var bSpan = data.spans[b];
          var tmp = aSpan.headFragment.from + aSpan.headFragment.to - bSpan.headFragment.from - bSpan.headFragment.to;
          if (tmp) {
            return tmp < 0 ? -1 : 1;
          }
          return 0;
        };
        $.each(sourceData.equivs, function(equivNo, equiv) {
          // equiv: ['*', 'Equiv', spanId...]
          equiv[0] = "*" + equivNo;
          var equivSpans = equiv.slice(2);
          var okEquivSpans = [];
          // collect the equiv spans in an array
          $.each(equivSpans, function(equivSpanNo, equivSpan) {
            if (data.spans[equivSpan]) okEquivSpans.push(equivSpan);
            // TODO: #404, inform the user with a message?
          });
          // sort spans in the equiv by their midpoint
          okEquivSpans.sort(spanComparator);
          // generate the arcs
          var len = okEquivSpans.length;
          for (var i = 1; i < len; i++) {
            var eventDesc = data.eventDescs[equiv[0] + '*' + i] =
                //           (id,                  triggerId,           roles,                         klass)
                new EventDesc(okEquivSpans[i - 1], okEquivSpans[i - 1], [[equiv[1], okEquivSpans[i]]], 'equiv');
            eventDesc.leftSpans = okEquivSpans.slice(0, i);
            eventDesc.rightSpans = okEquivSpans.slice(i);
          }
        });
        $.each(sourceData.relations, function(relNo, rel) {
          // rel[2] is args, rel[2][a][0] is role and rel[2][a][1] is value for a in (0,1)
          var argsDesc = relationTypesHash[rel[1]];
          argsDesc = argsDesc && argsDesc.args;
          var t1, t2;
          if (argsDesc) {
            // sort the arguments according to the config
            var args = {}
            args[rel[2][0][0]] = rel[2][0][1];
            args[rel[2][1][0]] = rel[2][1][1];
            t1 = args[argsDesc[0].role];
            t2 = args[argsDesc[1].role];
          } else {
            // (or leave as-is in its absence)
            t1 = rel[2][0][1];
            t2 = rel[2][1][1];
          }
          data.eventDescs[rel[0]] =
              //           (id, triggerId, roles,          klass)
              new EventDesc(t1, t1,        [[rel[1], t2]], 'relation');
        });

        // attributes
        $.each(sourceData.attributes, function(attrNo, attr) {
          // attr: [id, name, spanId, value, cueSpanId

          // TODO: might wish to check what's appropriate for the type
          // instead of using the first attribute def found
          var attrType = (eventAttributeTypes[attr[1]] ||
                          entityAttributeTypes[attr[1]]);
          var attrValue = attrType && attrType.values.byName[attrType.bool || attr[3]];
          var span = data.spans[attr[2]];
          if (!span) {
            dispatcher.post('messages', [[['Annotation ' + attr[2] + ', referenced from attribute ' + attr[0] + ', does not exist.', 'error']]]);
            return;
          }
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

        // comments
        $.each(sourceData.comments, function(commentNo, comment) {
          // comment: [entityId, type, text]

          // TODO error handling

          if (typeof comment[0] == 'string' && comment[0].indexOf(':') != -1) {
            comment[0] = comment[0].split(':');
          }
          // sentence id: ['sent', sentId]
          if (comment[0] instanceof Array && comment[0][0] == 'sent') {
            // sentence comment
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
                ? trigger[1] // trigger: [span, ...]
                : id in data.spans
                  ? [data.spans[id]] // span: [span]
                  : id in data.eventDescs
                    ? [data.eventDescs[id]] // arc: [eventDesc]
                    : [];
            $.each(commentEntities, function(entityId, entity) {
              // if duplicate comment for entity:
              // overwrite type, concatenate comment with a newline
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

        // normalizations
        $.each(sourceData.normalizations, function(normNo, norm) {
          var id = norm[0];
          var normType = norm[1];
          var target = norm[2];
          var refdb = norm[3];
          var refid = norm[4];
          var reftext = norm[5];

          // grab entity / event the normalization applies to
          var span = data.spans[target];
          if (!span) {
            dispatcher.post('messages', [[['Annotation ' + target + ', referenced from normalization ' + id + ', does not exist.', 'error']]]);
            return;
          }

          // TODO: do we have any possible use for the normType?
          span.normalizations.push([refdb, refid, reftext]);

          // quick hack for span box visual style
          span.normalized = 'Normalized';
        });

        // assign arcs to spans; calculate arc distances
        $.each(data.eventDescs, function(eventNo, eventDesc) {
          var dist = 0;
          var origin = data.spans[eventDesc.id];
          if (!origin) {
            // TODO: include missing trigger ID in error message
            dispatcher.post('messages', [[['<strong>ERROR</strong><br/>Trigger for event "' + eventDesc.id + '" not found in ' + data.document + '<br/>(please correct the source data)', 'error', 5]]]);
            return;
          }
          var here = origin.headFragment.from + origin.headFragment.to;
          $.each(eventDesc.roles, function(roleNo, role) {
            var target = data.spans[role.targetId];
            if (!target) {
              dispatcher.post('messages', [[['<strong>ERROR</strong><br/>"' + role.targetId + '" (referenced from "' + eventDesc.id + '") not found in ' + data.document + '<br/>(please correct the source data)', 'error', 5]]]);
              return;
            }
            var there = target.headFragment.from + target.headFragment.to;
            var dist = Math.abs(here - there);
            var arc = new Arc(eventDesc, role, dist, eventNo);
            origin.totalDist += dist;
            origin.numArcs++;
            target.totalDist += dist;
            target.numArcs++;
            data.arcs.push(arc);
            target.incoming.push(arc);
            origin.outgoing.push(arc);
            // ID dict for easy access. TODO: have a function defining the
            // (origin,type,target)->id mapping (see also annotator_ui.js)
            var arcId = origin.id + '--' + role.type + '--' + target.id;
            data.arcById[arcId] = arc;
          }); // roles
        }); // eventDescs

        // highlighting
        markedText = [];
        setMarked('edited'); // set by editing process
        setMarked('focus'); // set by URL
        setMarked('matchfocus'); // set by search process, focused match
        setMarked('match'); // set by search process, other (non-focused) match

        $.each(data.spans, function(spanId, span) {
          // calculate average arc distances
          // average distance of arcs (0 for no arcs)
          span.avgDist = span.numArcs ? span.totalDist / span.numArcs : 0;
          lastSpan = span; // DELETETHIS

          // collect fragment texts into span texts
          var fragmentTexts = [];
          $.each(span.fragments, function(fragmentNo, fragment) {
            // TODO heuristics
            fragmentTexts.push(fragment.text);
          });
          span.text = fragmentTexts.join('');
        }); // data.spans

        for (var i = 0; i < 2; i++) {
          // preliminary sort to assign heights for basic cases
          // (first round) and cases resolved in the previous
          // round(s).
          $.each(data.chunks, function(chunkNo, chunk) {
            // sort
            chunk.fragments.sort(fragmentComparator);
            // renumber
            $.each(chunk.fragments, function(fragmentNo, fragment) {
              fragment.indexNumber = fragmentNo;
            });
          });
          // nix the sums, so we can sum again
          $.each(data.spans, function(spanNo, span) {
            span.refedIndexSum = 0;
          });
          // resolved cases will now have indexNumber set
          // to indicate their relative order. Sum those for referencing cases
          // for use in iterative resorting
          $.each(data.arcs, function(arcNo, arc) {
            data.spans[arc.origin].refedIndexSum += data.spans[arc.target].headFragment.indexNumber;
          });
        }

        // Final sort of fragments in chunks for drawing purposes
        // Also identify the marked text boundaries regarding chunks
        var sentenceNo = 0;
        $.each(data.chunks, function(chunkNo, chunk) {
          // and make the next sort take this into account. Note that this will
          // now resolve first-order dependencies between sort orders but not
          // second-order or higher.
          chunk.fragments.sort(fragmentComparator);
          $.each(chunk.fragments, function(fragmentNo, fragment) {
            fragment.drawOrder = fragmentNo;
          });
        });

        data.spanDrawOrderPermutation = Object.keys(data.spans);
        data.spanDrawOrderPermutation.sort(function(a, b) {
          var spanA = data.spans[a];
          var spanB = data.spans[b];

          // We're jumping all over the chunks, but it's enough that
          // we're doing everything inside each chunk in the right
          // order. should it become necessary to actually do these in
          // linear order, put in a similar condition for
          // spanX.headFragment.chunk.index; but it should not be
          // needed.

          var tmp = spanA.headFragment.drawOrder - spanB.headFragment.drawOrder;
          if (tmp) return tmp < 0 ? -1 : 1;

          return 0;
        });

        // resort the spans for linear order by center
        sortedFragments.sort(midpointComparator);

        // sort fragments into towers, calculate average arc distances
        var lastFragment = null;
        var towerId = -1;
        $.each(sortedFragments, function(i, fragment) {
          if (!lastFragment || (lastFragment.from != fragment.from || lastFragment.to != fragment.to)) {
            towerId++;
          }
          fragment.towerId = towerId;
          lastFragment = fragment;
        }); // sortedFragments

        // find curlies (only the first fragment drawn in a tower)
        $.each(data.spanDrawOrderPermutation, function(spanIdNo, spanId) {
          var span = data.spans[spanId];

          $.each(span.fragments, function(fragmentNo, fragment) {
            if (!data.towers[fragment.towerId]) {
              data.towers[fragment.towerId] = [];
              fragment.drawCurly = true;
              fragment.span.drawCurly = true;
            }
            data.towers[fragment.towerId].push(fragment);
          });
        });

        var spanAnnTexts = {};
        $.each(data.chunks, function(chunkNo, chunk) {
          chunk.markedTextStart = [];
          chunk.markedTextEnd = [];

          $.each(chunk.fragments, function(fragmentNo, fragment) {
            if (chunk.firstFragmentIndex == undefined) {
              chunk.firstFragmentIndex = fragment.towerId;
            }
            chunk.lastFragmentIndex = fragment.towerId;

            var spanLabels = Util.getSpanLabels(spanTypes, fragment.span.type);
            fragment.labelText = Util.spanDisplayForm(spanTypes, fragment.span.type);
            // Find the most appropriate label according to text width
            if (Configuration.abbrevsOn && spanLabels) {
              var labelIdx = 1; // first abbrev
              var maxLength = (fragment.to - fragment.from) / 0.8;
              while (fragment.labelText.length > maxLength &&
                  spanLabels[labelIdx]) {
                fragment.labelText = spanLabels[labelIdx];
                labelIdx++;
              }
            }

            var svgtext = svg.createText(); // one "text" element per row
            var postfixArray = [];
            var prefix = '';
            var postfix = '';
            var warning = false;
            $.each(fragment.span.attributes, function(attrType, valType) {
              // TODO: might wish to check what's appropriate for the type
              // instead of using the first attribute def found
              var attr = (eventAttributeTypes[attrType] ||
                          entityAttributeTypes[attrType]);
              if (!attr) {
                // non-existent type
                warning = true;
                return;
              }
              var val = attr.values.byName[attr.bool || valType];
              if (!val) {
                // non-existent value
                warning = true;
                return;
              }
              if ($.isEmptyObject(val)) {
                // defined, but lacks any visual presentation
                warning = true;
                return;
              }
              if (val.glyph) {
                if (val.position == "left") {
                  prefix = val.glyph + prefix;
                  var tspan_attrs = { 'class' : 'glyph' };
                  if (val.glyphColor) {
                    tspan_attrs.fill = val.glyphColor;
                  }
                  svgtext.span(val.glyph, tspan_attrs);
                } else { // XXX right is implied - maybe change
                  postfixArray.push([attr, val]);
                  postfix += val.glyph;
                }
              }
            });
            var text = fragment.labelText;
            if (prefix !== '') {
              text = prefix + ' ' + text;
              svgtext.string(' ');
            }
            svgtext.string(fragment.labelText);
            if (postfixArray.length) {
              text += ' ' + postfix;
              svgtext.string(' ');
              $.each(postfixArray, function(elNo, el) {
                var tspan_attrs = { 'class' : 'glyph' };
                if (el[1].glyphColor) {
                  tspan_attrs.fill = el[1].glyphColor;
                }
                svgtext.span(el[1].glyph, tspan_attrs);
              });
            }
            if (warning) {
              svgtext.span("#", { 'class': 'glyph attribute_warning' });
              text += ' #';
            }
            fragment.glyphedLabelText = text;

            if (!spanAnnTexts[text]) {
              spanAnnTexts[text] = true;
              data.spanAnnTexts[text] = svgtext;
            }
          }); // chunk.fragments
        }); // chunks

        var numChunks = data.chunks.length;
        // note the location of marked text with respect to chunks
        var startChunk = 0;
        var currentChunk;
        // sort by "from"; we don't need to sort by "to" as well,
        // because unlike spans, chunks are disjunct
        markedText.sort(function(a, b) {
          return Util.cmp(a[0], b[0]);
        });
        $.each(markedText, function(textNo, textPos) {
          var from = textPos[0];
          var to = textPos[1];
          var markedType = textPos[2];
          if (from < 0) from = 0;
          if (to < 0) to = 0;
          if (to >= data.text.length) to = data.text.length - 1;
          if (from > to) from = to;
          while (startChunk < numChunks) {
            var chunk = data.chunks[startChunk];
            if (from <= chunk.to) {
              chunk.markedTextStart.push([textNo, true, from - chunk.from, null, markedType]);
              break;
            }
            startChunk++;
          }
          if (startChunk == numChunks) {
            dispatcher.post('messages', [[['Wrong text offset', 'error']]]);
            return;
          }
          currentChunk = startChunk;
          while (currentChunk < numChunks) {
            var chunk = data.chunks[currentChunk];
            if (to <= chunk.to) {
              chunk.markedTextEnd.push([textNo, false, to - chunk.from]);
              break
            }
            currentChunk++;
          }
          if (currentChunk == numChunks) {
            dispatcher.post('messages', [[['Wrong text offset', 'error']]]);
            var chunk = data.chunks[data.chunks.length - 1];
            chunk.markedTextEnd.push([textNo, false, chunk.text.length]);
            return;
          }
        }); // markedText

        dispatcher.post('dataReady', [data]);
      };

      var resetData = function() {
        setData(sourceData);
        renderData();
      }

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
        var blurFilter = document.createElementNS(defs.namespaceURI, 'filter');
        blurFilter.setAttribute('id', 'Gaussian_Blur');
        var blur = document.createElementNS(defs.namespaceURI, 'feGaussianBlur');
        blur.setAttribute('in', 'SourceGraphic');
        blur.setAttribute('stdDeviation', '2');
        blurFilter.appendChild(blur);
        defs.appendChild(blurFilter);
        // var $blurFilter = $('<filter id="Gaussian_Blur"><feGaussianBlur in="SourceGraphic" stdDeviation="2" /></filter>');
        // svg.add(defs, $blurFilter);
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

        return new Measurements(widths, bbox.height, bbox.y);
      };

      var getTextAndSpanTextMeasurements = function() {
        // get the span text sizes
        var chunkTexts = {}; // set of span texts
        $.each(data.chunks, function(chunkNo, chunk) {
          chunk.row = undefined; // reset
          if (!chunkTexts.hasOwnProperty(chunk.text)) chunkTexts[chunk.text] = []
          var chunkText = chunkTexts[chunk.text];

          // here we also need all the spans that are contained in
          // chunks with this text, because we need to know the position
          // of the span text within the respective chunk text
          chunkText.push.apply(chunkText, chunk.fragments);
          // and also the markedText boundaries
          chunkText.push.apply(chunkText, chunk.markedTextStart);
          chunkText.push.apply(chunkText, chunk.markedTextEnd);
        });
        var textSizes = getTextMeasurements(
          chunkTexts,
          undefined,
          function(fragment, text) {
            if (fragment instanceof Fragment) { // it's a fragment!
              // measure the fragment text position in pixels
              var firstChar = fragment.from - fragment.chunk.from;
              if (firstChar < 0) {
                firstChar = 0;
                dispatcher.post('messages', [[['<strong>WARNING</strong>' +
                  '<br/> ' +
                  'The fragment [' + fragment.from + ', ' + fragment.to + '] (' + fragment.text + ') is not ' +
                  'contained in its designated chunk [' +
                  fragment.chunk.from + ', ' + fragment.chunk.to + '] most likely ' +
                  'due to the fragment starting or ending with a space, please ' +
                  'verify the sanity of your data since we are unable to ' +
                  'visualise this fragment correctly and will drop leading ' +
                  'space characters'
                  , 'warning', 15]]]);
              }
              var lastChar = fragment.to - fragment.chunk.from - 1;

              // Adjust for XML whitespace (#832, #1009)
              var textUpToFirstChar = fragment.chunk.text.substring(0, firstChar);
              var textUpToLastChar = fragment.chunk.text.substring(0, lastChar);
              var textUpToFirstCharUnspaced = textUpToFirstChar.replace(/\s\s+/g, ' ');
              var textUpToLastCharUnspaced = textUpToLastChar.replace(/\s\s+/g, ' ');
              firstChar -= textUpToFirstChar.length - textUpToFirstCharUnspaced.length;
              lastChar -= textUpToLastChar.length - textUpToLastCharUnspaced.length;

              var startPos, endPos;
              if (firstChar < fragment.chunk.text.length) {
                startPos = text.getStartPositionOfChar(firstChar).x;
              } else {
                startPos = text.getComputedTextLength();
              }
              endPos = (lastChar < firstChar)
                ? startPos
                : text.getEndPositionOfChar(lastChar).x;

              // In RTL mode, positions are negative (left to right)
              if (rtlmode) {
                startPos = -startPos;
                endPos = -endPos;
              }

              fragment.curly = {
                from: Math.min(startPos, endPos),
                to: Math.max(startPos, endPos)
              };
            } else { // it's markedText [id, start?, char#, offset, kind]
              var textUpToChar = text.textContent.substring(0, fragment[2]);
              var textUpToCharUnspaced = textUpToChar.replace(/\s\s+/g, ' ');
              var pos = fragment[2] - (textUpToChar.length - textUpToCharUnspaced.length);
              if (pos < 0) pos = 0;
              if (!pos) { // start
                fragment[3] = text.getStartPositionOfChar(pos).x;
              } else {
                fragment[3] = text.getEndPositionOfChar(pos - 1).x + 1;
              }
            }
          });

        // get the fragment annotation text sizes
        var fragmentTexts = {};
        var noSpans = true;
        $.each(data.spans, function(spanNo, span) {
          $.each(span.fragments, function(fragmentNo, fragment) {
            fragmentTexts[fragment.glyphedLabelText] = true;
            noSpans = false;
          });
        });
        if (noSpans) fragmentTexts.$ = true; // dummy so we can at least get the height
        var fragmentSizes = getTextMeasurements(fragmentTexts, {'class': 'span'});

        return {
          texts: textSizes,
          fragments: fragmentSizes
        };
      };

      var addArcTextMeasurements = function(sizes) {
        // get the arc annotation text sizes (for all labels)
        var arcTexts = {};
        $.each(data.arcs, function(arcNo, arc) {
          var labels = Util.getArcLabels(spanTypes, data.spans[arc.origin].type, arc.type, relationTypesHash);
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
          $.each(tower, function(fragmentNo, fragment) {
            var width = data.sizes.fragments.widths[fragment.glyphedLabelText];
            if (width > maxWidth) maxWidth = width;
          }); // tower
          $.each(tower, function(fragmentNo, fragment) {
            fragment.width = maxWidth;
          }); // tower
        }); // data.towers
      };

      var makeArrow = function(defs, spec) {
        var parsedSpec = spec.split(',');
        var type = parsedSpec[0];
        if (type == 'none') return;

        var width = 5;
        var height = 5;
        var color = "black";
        if ($.isNumeric(parsedSpec[1]) && parsedSpec[2]) {
          if ($.isNumeric(parsedSpec[2]) && parsedSpec[3]) {
            // 3 args, 2 numeric: assume width, height, color
            width = parsedSpec[1];
            height = parsedSpec[2];
            color = parsedSpec[3] || 'black';
          } else {
            // 2 args, 1 numeric: assume width/height, color
            width = height = parsedSpec[1];
            color = parsedSpec[2] || 'black';
          }
        } else {
          // other: assume color only
          width = height = 5;
          color = parsedSpec[1] || 'black';
        }
        // hash needs to be replaced as IDs don't permit it.
        var arrowId = 'arrow_' + spec.replace(/#/g, '').replace(/,/g, '_');

        var arrow;
        if (type == 'triangle') {
          arrow = svg.marker(defs, arrowId,
            width, height / 2, width, height, 'auto',
            {
              markerUnits: 'strokeWidth',
              'fill': color,
            });
          svg.polyline(arrow, [[0, 0], [width, height / 2], [0, height], [width / 12, height / 2]]);
        }
        return arrowId;
      }

      var createStyleMap = function(styles) {
          /* Given a list of [ID, attrib, value] lists, return dict of
             dicts d where d[ID][attrib] == value.
          */
          var styleMap = {};

          if (!styles) {
              return styleMap;
          }
          for (var i=0; i<styles.length; i++) {
              var style = styles[i];

              if (!style || style.length !== 3) {
                  console.log('warning: invalid style spec:', style);
                  continue;
              }

              var targetRef = style[0],
                  attribute = style[1],
                  value = style[2];

              // map multipart IDs to reference string by joining w/space
              if (targetRef instanceof Array) {
                  targetRef = targetRef.join(' ');
              }

              if (styleMap[targetRef] === undefined) {
                  styleMap[targetRef] = {};
              }
              if (styleMap[targetRef][attribute] !== undefined) {
                  console.log('warning: multiple style definitions for',
                              targetRef, attribute);
              }
              styleMap[targetRef][attribute] = value;
          }
          return styleMap;
      };

      var drawing = false;
      var redraw = false;

      var renderDataReal = function(sourceData) {
Util.profileEnd('before render');
Util.profileStart('render');
Util.profileStart('init');

        if (!sourceData && !data) {
          dispatcher.post('doneRendering', [coll, doc, args]);
          return;
        }
        $svgDiv.show();
        if ((sourceData && sourceData.collection && (sourceData.document !== doc || sourceData.collection !== coll)) || drawing) {
          redraw = true;
          dispatcher.post('doneRendering', [coll, doc, args]);
          return;
        }
        redraw = false;
        drawing = true;

        if (sourceData) setData(sourceData);
        showMtime();

        // clear the SVG
        svg.clear(true);
        if (!data || data.length == 0) return;

        // establish the width according to the enclosing element
        canvasWidth = that.forceWidth || $svgDiv.width();

        var defs = addHeaderAndDefs();

        var backgroundGroup = svg.group({ 'class': 'background' });
        var glowGroup = svg.group({ 'class': 'glow' });
        highlightGroup = svg.group({ 'class': 'highlight' });
        var textGroup = svg.group({ 'class': 'text' });

Util.profileEnd('init');
Util.profileStart('measures');

        var sizes = getTextAndSpanTextMeasurements();
        data.sizes = sizes;

        var styleMap = createStyleMap(data.styles);

        adjustTowerAnnotationSizes();
        var maxTextWidth = 0;
        for (var text in sizes.texts.widths) {
          if (sizes.texts.widths.hasOwnProperty(text)) {
            var width = sizes.texts.widths[text]
            if (width > maxTextWidth) maxTextWidth = width;
          }
        }

Util.profileEnd('measures');
Util.profileStart('chunks');

        // var currentX = Configuration.visual.margin.x + sentNumMargin + rowPadding;
        var currentX;
        if (rtlmode) {
          currentX = canvasWidth - (Configuration.visual.margin.x + sentNumMargin + rowPadding);
        } else {
          currentX = Configuration.visual.margin.x + sentNumMargin + rowPadding;
        }

        var rows = [];
        var fragmentHeights = [];
        var sentenceToggle = 0;
        var rowIndex = 0;
        var sentenceNumber = pagingOffset ? pagingOffset - 1 : 0;
        var row = new Row(svg);
        row.sentence = ++sentenceNumber;
        row.backgroundIndex = sentenceToggle;
        row.index = rowIndex;
        var twoBarWidths; // HACK to avoid measuring space's width
        var openTextHighlights = {};
        var textMarkedRows = [];

        addArcTextMeasurements(sizes);

        // reserve places for spans
        var floors = [];
        var reservations = []; // reservations[chunk][floor] = [[from, to, headroom]...]
        for (var i = 0; i <= data.lastFragmentIndex; i++) {
          reservation[i] = {};
        }
        var inf = 1.0/0.0;

        $.each(data.spanDrawOrderPermutation, function(spanIdNo, spanId) {
          var span = data.spans[spanId];
          var spanDesc = spanTypes[span.type];
          var bgColor = ((spanDesc && spanDesc.bgColor) ||
                          (spanTypes.SPAN_DEFAULT &&
                          spanTypes.SPAN_DEFAULT.bgColor) || '#ffffff');
          if (bgColor == "hidden") {
            span.hidden = true;
            return;
          }

          var f1 = span.firstFragment, f2 = span.lastFragment;

          var x1 = (f1.curly.from + f1.curly.to - f1.width) / 2 -
              Configuration.visual.margin.x;
          var i1 = f1.chunk.index;

          var x2 = (f2.curly.from + f2.curly.to + f2.width) / 2 +
              Configuration.visual.margin.x;
          var i2 = f2.chunk.index;

          // Start from the ground level, going up floor by floor.
          // If no more floors, make a new available one.
          // If a floor is available and there is no carpet, mark it as carpet.
          // If a floor is available and there is carpet and height
          //   difference is at least fragment height + curly, OK.
          // If a floor is not available, forget about carpet.
          // --
          // When OK, calculate exact ceiling.
          // If there isn't one, make a new floor, copy reservations
          //   from floor below (with decreased ceiling)
          // Make the reservation from the carpet to just below the
          //   current floor.
          //
          // TODO drawCurly and height could be prettified to only check
          // actual positions of curlies
          var carpet = 0;
          var outside = true;
          var thisCurlyHeight = span.drawCurly ? Configuration.visual.curlyHeight : 0;
          var height = sizes.fragments.height + thisCurlyHeight + Configuration.visual.boxSpacing +
              2 * Configuration.visual.margin.y - 3;
          $.each(floors, function(floorNo, floor) {
            var floorAvailable = true;
            for (var i = i1; i <= i2; i++) {
              if (!(reservations[i] && reservations[i][floor])) continue;
              var from = (i == i1) ? x1 : -inf;
              var to = (i == i2) ? x2 : inf;
              $.each(reservations[i][floor], function(resNo, res) {
                if (res[0] < to && from < res[1]) {
                  floorAvailable = false;
                  return false;
                }
              });
            }
            if (floorAvailable) {
              if (carpet === null) {
                carpet = floor;
              } else if (height + carpet <= floor) {
                // found our floor!
                outside = false;
                return false;
              }
            } else {
              carpet = null;
            }
          });
          var reslen = reservations.length;
          var makeNewFloorIfNeeded = function(floor) {
            var floorNo = $.inArray(floor, floors);
            if (floorNo == -1) {
              floors.push(floor);
              floors.sort(Util.cmp);
              floorNo = $.inArray(floor, floors);
              if (floorNo != 0) {
                // copy reservations from the floor below
                var parquet = floors[floorNo - 1];
                for (var i = 0; i <= reslen; i++) {
                  if (reservations[i]) {
                    if (!reservations[i][parquet]) {
                      reservations[i][parquet] = [];
                    }
                    var footroom = floor - parquet;
                    $.each(reservations[i][parquet], function(resNo, res) {
                      if (res[2] > footroom) {
                        if (!reservations[i][floor]) {
                          reservations[i][floor] = [];
                        }
                        reservations[i][floor].push([res[0], res[1], res[2] - footroom]);
                      }
                    });
                  }
                }
              }
            }
            return floorNo;
          }
          var ceiling = carpet + height;
          var ceilingNo = makeNewFloorIfNeeded(ceiling);
          var carpetNo = makeNewFloorIfNeeded(carpet);
          // make the reservation
          var floor, floorNo;
          for (floorNo = carpetNo;
              (floor = floors[floorNo]) !== undefined && floor < ceiling;
              floorNo++) {
            var headroom = ceiling - floor;
            for (var i = i1; i <= i2; i++) {
              var from = (i == i1) ? x1 : 0;
              var to = (i == i2) ? x2 : inf;
              if (!reservations[i]) reservations[i] = {};
              if (!reservations[i][floor]) reservations[i][floor] = [];
              reservations[i][floor].push([from, to, headroom]); // XXX maybe add fragment; probably unnecessary
            }
          }
          span.floor = carpet + thisCurlyHeight;
        });

        var firstChunk, lastChunk;
        $.each(data.chunks, function(chunkNo, chunk) {
          if (chunk.outOfPage) return;
          if (!firstChunk) {
            firstChunk = chunk;
            if (chunkNo) row.sentence++;
            while (sentenceNumber < chunk.sentence) {
              sentenceNumber++;
              rows.push(row);
              row = new Row(svg);
              sentenceToggle = 1 - sentenceToggle;
              row.backgroundIndex = sentenceToggle;
              row.index = ++rowIndex;
            }
            // sentenceToggle = 1 - sentenceToggle;
          }
          lastChunk = chunk;

          var spaceWidth = 0;
          if (chunk.lastSpace) {
            var spaceLen = chunk.lastSpace.length || 0;
            var spacePos = chunk.lastSpace.lastIndexOf("\n") + 1;
            if (spacePos || !chunkNo || !chunk.sentence) {
              // indent if
              // * non-first paragraph first word
              // * first paragraph first word
              // * non-first word in a line
              // don't indent if
              // * the first word in a non-paragraph line
              for (var i = spacePos; i < spaceLen; i++) spaceWidth += spaceWidths[chunk.lastSpace.charAt(i)] || 0;
              currentX += rtlmode ? -spaceWidth : spaceWidth;
            }
          }

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

          $.each(chunk.fragments, function(fragmentNo, fragment) {
            var span = fragment.span;
            var spanDesc = spanTypes[span.type];
            var bgColor = ((spanDesc && spanDesc.bgColor) ||
                           (spanTypes.SPAN_DEFAULT &&
                            spanTypes.SPAN_DEFAULT.bgColor) || '#ffffff');
            if (span.hidden) return;
            var fgColor = ((spanDesc && spanDesc.fgColor) ||
                           (spanTypes.SPAN_DEFAULT &&
                            spanTypes.SPAN_DEFAULT.fgColor) || '#000000');
            var borderColor = ((spanDesc && spanDesc.borderColor) ||
                               (spanTypes.SPAN_DEFAULT &&
                                spanTypes.SPAN_DEFAULT.borderColor) || '#000000');

            // set span-specific styles
            if (styleMap[span.id]) {
                if (styleMap[span.id]['fgColor'] !== undefined) {
                    fgColor = styleMap[span.id]['fgColor'];
                }
                if (styleMap[span.id]['bgColor'] !== undefined) {
                    bgColor = styleMap[span.id]['bgColor'];
                }
                if (styleMap[span.id]['borderColor'] !== undefined) {
                    borderColor = styleMap[span.id]['borderColor'];
                }
            }

            // special case: if the border 'color' value is 'darken',
            // then just darken the BG color a bit for the border.
            if (borderColor == 'darken') {
                borderColor = Util.adjustColorLightness(bgColor, -0.6);
            }

            fragment.group = svg.group(chunk.group, {
              'class': 'span',
            });

            var fragmentHeight = 0;

            if (!y) y = -sizes.texts.height;
            var x = (fragment.curly.from + fragment.curly.to) / 2;

            // XXX is it maybe sizes.texts?
            var yy = y + sizes.fragments.y;
            var hh = sizes.fragments.height;
            var ww = fragment.width;
            var xx = x - ww / 2;

            // text margin fine-tuning
            yy += boxTextMargin.y;
            hh -= 2*boxTextMargin.y;
            xx += boxTextMargin.x;
            ww -= 2*boxTextMargin.x;
            var rectClass = 'span_' + (span.cue || span.type) + ' span_default'; // TODO XXX first part unneeded I think; remove

            // attach e.g. "False_positive" into the type
            if (span.comment && span.comment.type) { rectClass += ' '+span.comment.type; }
            var bx = xx - Configuration.visual.margin.x - boxTextMargin.x;
            var by = yy - Configuration.visual.margin.y;
            var bw = ww + 2 * Configuration.visual.margin.x;
            var bh = hh + 2 * Configuration.visual.margin.y;

            if (roundCoordinates) {
              x  = (x|0)+0.5;
              bx = (bx|0)+0.5;
            }

            var shadowRect;
            var markedRect;
            if (span.marked) {
              markedRect = svg.rect(chunk.highlightGroup,
                  bx - markedSpanSize, by - markedSpanSize,
                  bw + 2 * markedSpanSize, bh + 2 * markedSpanSize, {

                  // filter: 'url(#Gaussian_Blur)',
                  'class': "shadow_EditHighlight",
                  rx: markedSpanSize,
                  ry: markedSpanSize,
              });
              svg.other(markedRect, 'animate', {
                'data-type': span.marked,
                attributeName: 'fill',
                values: (span.marked == 'match'? highlightMatchSequence
                         : highlightSpanSequence),
                dur: highlightDuration,
                repeatCount: 'indefinite',
                begin: 'indefinite'
              });
              chunkFrom = Math.min(bx - markedSpanSize, chunkFrom);
              chunkTo = Math.max(bx + bw + markedSpanSize, chunkTo);
              fragmentHeight = Math.max(bh + 2 * markedSpanSize, fragmentHeight);
            }
            // .match() removes unconfigured shadows, which were
            // always showing up as black.
            // TODO: don't hard-code configured shadowclasses.
            if (span.shadowClass &&
                span.shadowClass.match('True_positive|False_positive|False_negative|AnnotationError|AnnotationWarning|AnnotatorNotes|Normalized|AnnotationIncomplete|AnnotationUnconfirmed|rectEditHighlight|EditHighlight_arc|MissingAnnotation|ChangedAnnotation ')) {
              shadowRect = svg.rect(fragment.group,
                  bx - rectShadowSize, by - rectShadowSize,
                  bw + 2 * rectShadowSize, bh + 2 * rectShadowSize, {
                  'class': 'shadow_' + span.shadowClass,
                  filter: 'url(#Gaussian_Blur)',
                  rx: rectShadowRounding,
                  ry: rectShadowRounding,
              });
              chunkFrom = Math.min(bx - rectShadowSize, chunkFrom);
              chunkTo = Math.max(bx + bw + rectShadowSize, chunkTo);
              fragmentHeight = Math.max(bh + 2 * rectShadowSize, fragmentHeight);
            }
            fragment.rect = svg.rect(fragment.group,
                bx, by, bw, bh, {

                'class': rectClass,
                fill: bgColor,
                stroke: borderColor,
                rx: Configuration.visual.margin.x,
                ry: Configuration.visual.margin.y,
                'data-span-id': span.id,
                'data-fragment-id': span.segmentedOffsetsMap[fragment.id],
                'strokeDashArray': span.attributeMerge.dashArray,
              });

            // TODO XXX: quick nasty hack to allow normalizations
            // to be marked visually; do something cleaner!
            if (span.normalized) {
              $(fragment.rect).addClass(span.normalized);
            }

            fragment.left = bx; // TODO put it somewhere nicer? // XXX RTL needed?
            fragment.right = bx + bw; // TODO put it somewhere nicer?
            if (!(span.shadowClass || span.marked)) {
              chunkFrom = Math.min(bx, chunkFrom);
              chunkTo = Math.max(bx + bw, chunkTo);
              fragmentHeight = Math.max(bh, fragmentHeight);
            }

            fragment.rectBox = { x: bx, y: by - span.floor, width: bw, height: bh };
            fragment.height = span.floor + hh + 3 * Configuration.visual.margin.y + Configuration.visual.curlyHeight + Configuration.visual.arcSpacing;
            var spacedTowerId = fragment.towerId * 2;
            if (!fragmentHeights[spacedTowerId] || fragmentHeights[spacedTowerId] < fragment.height) {
              fragmentHeights[spacedTowerId] = fragment.height;
            }
            $(fragment.rect).attr('y', yy - Configuration.visual.margin.y - span.floor);
            if (shadowRect) {
              $(shadowRect).attr('y', yy - rectShadowSize - Configuration.visual.margin.y - span.floor);
            }
            if (markedRect) {
              $(markedRect).attr('y', yy - markedSpanSize - Configuration.visual.margin.y - span.floor);
            }
            if (span.attributeMerge.box === "crossed") {
              svg.path(fragment.group, svg.createPath().
                  move(xx, yy - Configuration.visual.margin.y - span.floor).
                  line(xx + fragment.width,
                    yy + hh + Configuration.visual.margin.y - span.floor),
                  { 'class': 'boxcross' });
              svg.path(fragment.group, svg.createPath().
                  move(xx + fragment.width, yy - Configuration.visual.margin.y - span.floor).
                  line(xx, yy + hh + Configuration.visual.margin.y - span.floor),
                  { 'class': 'boxcross' });
            }
            svg.text(fragment.group, x, y - span.floor, data.spanAnnTexts[fragment.glyphedLabelText], { fill: fgColor });

            // Make curlies to show the fragment
            if (fragment.drawCurly) {
              var curlyColor = 'grey';
              if (coloredCurlies) {
                var spanDesc = spanTypes[span.type];
                var bgColor = ((spanDesc && spanDesc.bgColor) ||
                               (spanTypes.SPAN_DEFAULT &&
                                spanTypes.SPAN_DEFAULT.fgColor) ||
                               '#000000');
                curlyColor = Util.adjustColorLightness(bgColor, -0.6);
              }

              var bottom = yy + hh + Configuration.visual.margin.y - span.floor + 1;
              svg.path(fragment.group, svg.createPath()
                  .move(fragment.curly.from, bottom + Configuration.visual.curlyHeight)
                  .curveC(fragment.curly.from, bottom,
                    x, bottom + Configuration.visual.curlyHeight,
                    x, bottom)
                  .curveC(x, bottom + Configuration.visual.curlyHeight,
                    fragment.curly.to, bottom,
                    fragment.curly.to, bottom + Configuration.visual.curlyHeight),
                {
                  'class': 'curly',
                  'stroke': curlyColor,
                });
              chunkFrom = Math.min(fragment.curly.from, chunkFrom);
              chunkTo = Math.max(fragment.curly.to, chunkTo);
              fragmentHeight = Math.max(Configuration.visual.curlyHeight, fragmentHeight);
            }

            if (fragment == span.headFragment) {
              // find the gap to fit the backwards arcs, but only on
              // head fragment - other fragments don't have arcs
              $.each(span.incoming, function(arcId, arc) {
                var leftSpan = data.spans[arc.origin];
                var origin = leftSpan.headFragment.chunk;
                var border;
                if (chunk.index == origin.index) {
                  hasInternalArcs = true;
                }
                if (origin.row) {
                  var labels = Util.getArcLabels(spanTypes, leftSpan.type, arc.type, relationTypesHash);
                  if (!labels.length) labels = [arc.type];
                  if (origin.row.index == rowIndex) {
                    // same row, but before this
                    border = origin.translation.x + leftSpan.fragments[leftSpan.fragments.length - 1].right;
                  } else if (rtlmode) {
                    border = 0;
                  } else {
                    border = Configuration.visual.margin.x + sentNumMargin + rowPadding;
                  }
                  var labelNo = Configuration.abbrevsOn ? labels.length - 1 : 0;
                  var smallestLabelWidth = sizes.arcs.widths[labels[labelNo]] + 2 * minArcSlant;
                  var gap = Math.abs(currentX + (rtlmode ? -bx : bx) - border);
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
                var target = leftSpan.headFragment.chunk;
                var border;
                if (target.row) {
                  var labels = Util.getArcLabels(spanTypes, span.type, arc.type, relationTypesHash);
                  if (!labels.length) labels = [arc.type];
                  if (target.row.index == rowIndex) {
                    // same row, but before this
                    border = target.translation.x + leftSpan.fragments[leftSpan.fragments.length - 1].right;
                  } else if (rtlmode) {
                    border = 0;
                  } else {
                    border = Configuration.visual.margin.x + sentNumMargin + rowPadding;
                  }
                  var labelNo = Configuration.abbrevsOn ? labels.length - 1 : 0;
                  var smallestLabelWidth = sizes.arcs.widths[labels[labelNo]] + 2 * minArcSlant;
                  var gap = Math.abs(currentX + (rtlmode ? -bx : bx) - border);
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
            }
            fragmentHeight += span.floor || Configuration.visual.curlyHeight;
            if (fragmentHeight > chunkHeight) chunkHeight = fragmentHeight;
            hasAnnotations = true;
          }); // fragments

          // positioning of the chunk
          chunk.right = chunkTo;
          var textWidth = sizes.texts.widths[chunk.text];
          chunkHeight += sizes.texts.height;
          var boxX = rtlmode ? chunkTo : -Math.min(chunkFrom, 0);
          var boxWidth;
          if (rtlmode) {
            boxWidth = Math.max(textWidth, -chunkFrom) - Math.min(0, -chunkTo);
          } else {
            boxWidth = Math.max(textWidth, chunkTo) - Math.min(0, chunkFrom);
          }
          // if (hasLeftArcs) {
            // TODO change this with smallestLeftArc
            // var spacing = arcHorizontalSpacing - (currentX - lastArcBorder);
            // arc too small?
          if (spacing > 0) {
            currentX += rtlmode ? -spacing : spacing;
          }
          // }
          var rightBorderForArcs = hasRightArcs ? arcHorizontalSpacing : (hasInternalArcs ? arcSlant : 0);
          var leftBorderForArcs = hasLeftArcs ? arcHorizontalSpacing : (hasInternalArcs ? arcSlant : 0);

          var lastX = currentX;
          var lastRow = row;

          if (chunk.sentence && chunk != firstChunk) {
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

          var chunkDoesNotFit;
          if (rtlmode) {
            chunkDoesNotFit = currentX - boxWidth - leftBorderForArcs <= 2 * Configuration.visual.margin.x;
          } else {
            chunkDoesNotFit = currentX + boxWidth + rightBorderForArcs >= canvasWidth - 2 * Configuration.visual.margin.x
          }

          if (chunk.sentence || chunkDoesNotFit) {
            row.arcs = svg.group(row.group, { 'class': 'arcs' });
            // TODO: related to issue #571
            // replace arcHorizontalSpacing with a calculated value

            // XXX RTL spaceWidth?
            if (rtlmode) {
              currentX = canvasWidth - (Configuration.visual.margin.x + sentNumMargin + rowPadding +
                  (hasRightArcs ? arcHorizontalSpacing : (hasInternalArcs ? arcSlant : 0))/* + spaceWidth */ );
            } else {
              currentX = Configuration.visual.margin.x + sentNumMargin + rowPadding +
                  (hasLeftArcs ? arcHorizontalSpacing : (hasInternalArcs ? arcSlant : 0)) /* + spaceWidth */ ;
            }

            if (hasLeftArcs) {
              var adjustedCurTextWidth = sizes.texts.widths[chunk.text] + arcHorizontalSpacing;
              if (adjustedCurTextWidth > maxTextWidth) {
                maxTextWidth = adjustedCurTextWidth;
              }
            }
            if (spacingRowBreak > 0) {
              currentX += rtlmode ? -spacingRowBreak : spacingRowBreak;
              spacing = 0; // do not center intervening elements
            }

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
                  chunk.fragments[index].group = element;
              });
            $(chunk.group).find("rect[data-span-id]").
              each(function(index, element) {
                  chunk.fragments[index].rect = element;
              });
          }

          // break the text highlights when the row breaks
          if (row.index !== lastRow.index) {
            $.each(openTextHighlights, function(textId, textDesc) {
              if (textDesc[3] != lastX) {
                var newDesc = [lastRow, textDesc[3], lastX + (rtlmode ? -boxX : boxX), textDesc[4]];
                textMarkedRows.push(newDesc);
              }
              textDesc[3] = currentX;
            });
          }

          // open text highlights
          $.each(chunk.markedTextStart, function(textNo, textDesc) {
            textDesc[3] += currentX + (rtlmode ? -boxX : boxX);
            openTextHighlights[textDesc[0]] = textDesc;
          });

          // close text highlights
          $.each(chunk.markedTextEnd, function(textNo, textDesc) {
            textDesc[3] += currentX + (rtlmode ? -boxX : boxX);
            var startDesc = openTextHighlights[textDesc[0]];
            delete openTextHighlights[textDesc[0]];
            markedRow = [row, startDesc[3], textDesc[3], startDesc[4]];
            textMarkedRows.push(markedRow);
          });

          // XXX check this - is it used? should it be lastRow?
          if (hasAnnotations) row.hasAnnotations = true;

          if (chunk.sentence) {
            row.sentence = ++sentenceNumber;
          }

          if (spacing > 0) {
            // if we added a gap, center the intervening elements
            spacing /= 2;
            var firstChunkInRow = row.chunks[row.chunks.length - 1];
            // are there already some intervening chunks to move?
            if (firstChunkInRow) {
              if (spacingChunkId < firstChunkInRow.index) {
                spacingChunkId = firstChunkInRow.index + 1;
              }
              for (var chunkIndex = spacingChunkId; chunkIndex < chunk.index; chunkIndex++) {
                var movedChunk = data.chunks[chunkIndex];
                translate(movedChunk, movedChunk.translation.x + spacing, 0);
                movedChunk.textX += spacing;
              }
            }
          }

          row.chunks.push(chunk);
          chunk.row = row;

          translate(chunk, currentX + (rtlmode ? -boxX : boxX), 0);
          chunk.textX = currentX + (rtlmode ? -boxX : boxX);

          currentX += rtlmode ? -boxWidth : boxWidth;
        }); // chunks

        if (!lastChunk) {
          // nothing here
          drawing = false;
          dispatcher.post('doneRendering', [coll, doc, args]);
          return;
        }

        // finish the last row
        row.arcs = svg.group(row.group, { 'class': 'arcs' });
        rows.push(row);

Util.profileEnd('chunks');
Util.profileStart('arcsPrep');

        var arrows = {};
        var arrow = makeArrow(defs, 'none');
        if (arrow) arrows['none'] = arrow;

        var len = lastChunk.index * 2 + 1;
        for (var i = 0; i < len; i++) {
          if (!fragmentHeights[i] || fragmentHeights[i] < Configuration.visual.arcStartHeight) {
            fragmentHeights[i] = Configuration.visual.arcStartHeight;
          }
        }

        // find out how high the arcs have to go
        $.each(data.arcs, function(arcNo, arc) {
          arc.jumpHeight = 0;
          var fromFragment = data.spans[arc.origin].headFragment;
          var toFragment = data.spans[arc.target].headFragment;
          if (fromFragment.span.hidden || toFragment.span.hidden) {
            arc.hidden = true;
            return;
          }
          if (fromFragment.towerId > toFragment.towerId) {
            var tmp = fromFragment; fromFragment = toFragment; toFragment = tmp;
          }
          var from, to;
          if (fromFragment.chunk.index == toFragment.chunk.index) {
            from = fromFragment.towerId;
            to = toFragment.towerId;
          } else {
            from = fromFragment.towerId + 1;
            to = toFragment.towerId - 1;
          }
          for (var i = from; i <= to; i++) {
            if (arc.jumpHeight < fragmentHeights[i * 2]) arc.jumpHeight = fragmentHeights[i * 2];
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
          tmp = data.spans[a.origin].headFragment.height + data.spans[a.target].headFragment.height -
            data.spans[b.origin].headFragment.height - data.spans[b.target].headFragment.height;
          if (tmp) return tmp < 0 ? -1 : 1;
          // if equal, then those with the lower origin
          tmp = data.spans[a.origin].headFragment.height - data.spans[b.origin].headFragment.height;
          if (tmp) return tmp < 0 ? -1 : 1;
          // if equal, they're just equal.
          return 0;
        });

        // see which fragments are in each row
        var heightsStart = 0;
        var heightsRowsAdded = 0;
        $.each(rows, function(rowId, row) {
          var seenFragment = false;
          row.heightsStart = row.heightsEnd = heightsStart;
          $.each(row.chunks, function(chunkId, chunk) {
            if (chunk.lastFragmentIndex !== undefined) {
              // fragmentful chunk
              seenFragment = true;
              var heightsIndex = chunk.lastFragmentIndex * 2 + heightsRowsAdded;
              if (row.heightsEnd < heightsIndex) {
                row.heightsEnd = heightsIndex;
              }
              var heightsIndex = chunk.firstFragmentIndex * 2 + heightsRowsAdded;
              if (row.heightsStart > heightsIndex) {
                row.heightsStart = heightsIndex;
              }
            }
          });
          fragmentHeights.splice(row.heightsStart, 0, Configuration.visual.arcStartHeight);
          heightsRowsAdded++;

          row.heightsAdjust = heightsRowsAdded;
          if (seenFragment) {
            row.heightsEnd += 2;
          }
          heightsStart = row.heightsEnd + 1;
        });

        // draw the drag arc marker
        var arrowhead = svg.marker(defs, 'drag_arrow',
          5, 2.5, 5, 5, 'auto',
          {
            markerUnits: 'strokeWidth',
            'class': 'drag_fill',
          });
        svg.polyline(arrowhead, [[0, 0], [5, 2.5], [0, 5], [0.2, 2.5]]);
        var arcDragArc = svg.path(svg.createPath(), {
          markerEnd: 'url(#drag_arrow)',
          'class': 'drag_stroke',
          fill: 'none',
          visibility: 'hidden',
        });
        dispatcher.post('arcDragArcDrawn', [arcDragArc]);

Util.profileEnd('arcsPrep');
Util.profileStart('arcs');

        var arcCache = {};
        // add the arcs
        $.each(data.arcs, function(arcNo, arc) {
          if (arc.hidden) return;

          var originSpan = data.spans[arc.origin];
          var targetSpan = data.spans[arc.target];

          // separate out possible numeric suffix from type
          var noNumArcType;
          var splitArcType;
          if (arc.type) {
            splitArcType = arc.type.match(/^(.*?)(\d*)$/);
            noNumArcType = splitArcType[1];
          }

          var leftToRight = originSpan.headFragment.towerId < targetSpan.headFragment.towerId;
          var left, right;
          if (leftToRight) {
            left = originSpan.headFragment;
            right = targetSpan.headFragment;
          } else {
            left = targetSpan.headFragment;
            right = originSpan.headFragment;
          }

          var leftPos = left.chunk.outOfPage;
          var rightPos = right.chunk.outOfPage;
          if (leftPos && rightPos) return;

          // fall back on relation types in case we still don't have
          // an arc description, with final fallback to unnumbered relation
          var arcDesc = relationTypesHash[arc.type] || relationTypesHash[noNumArcType];

          // if it's not a relationship, see if we can find it in span
          // descriptions
          // TODO: might make more sense to reformat this as dict instead
          // of searching through the list every type
          var spanDesc = spanTypes[originSpan.type];
          if (!arcDesc && spanDesc && spanDesc.arcs) {
            $.each(spanDesc.arcs, function(arcDescNo, arcDescIter) {
                if (arcDescIter.type == arc.type) {
                  arcDesc = arcDescIter;
                }
              });
          }
          // last fall back on unnumbered type if not found in full
          if (!arcDesc && noNumArcType && noNumArcType != arc.type &&
            spanDesc && spanDesc.arcs) {
            $.each(spanDesc.arcs, function(arcDescNo, arcDescIter) {
                if (arcDescIter.type == noNumArcType) {
                  arcDesc = arcDescIter;
                }
              });
          }
          // empty default
          if (!arcDesc) arcDesc = {};

          var color = ((arcDesc && arcDesc.color) ||
                       (spanTypes.ARC_DEFAULT && spanTypes.ARC_DEFAULT.color) ||
                       '#000000');
          if (color == 'hidden') return;
          var symmetric = arcDesc && arcDesc.properties && arcDesc.properties.symmetric;
          var dashArray = arcDesc && arcDesc.dashArray;
          var arrowHead = ((arcDesc && arcDesc.arrowHead) ||
                           (spanTypes.ARC_DEFAULT && spanTypes.ARC_DEFAULT.arrowHead) ||
                           'triangle,5');
          var labelArrowHead = ((arcDesc && arcDesc.labelArrow) ||
                                (spanTypes.ARC_DEFAULT && spanTypes.ARC_DEFAULT.labelArrow) ||
                                'triangle,5');

          // set arc-specific styles
          var arcRef = [arc.origin, arc.target, arc.type].join(' ');
          if (styleMap[arcRef]) {
              if (styleMap[arcRef]['color'] !== undefined) {
                  color = styleMap[arcRef]['color'];
              }
              if (styleMap[arcRef]['symmetric'] !== undefined) {
                  symmetric = styleMap[arcRef]['symmetric'];
              }
              if (styleMap[arcRef]['dashArray'] !== undefined) {
                  dashArray = styleMap[arcRef]['dashArray'];
              }
              if (styleMap[arcRef]['arrowHead'] !== undefined) {
                  arrowHead = styleMap[arcRef]['arrowHead'];
              }
              if (styleMap[arcRef]['labelArrow'] !== undefined) {
                  labelArrowHead = styleMap[arcRef]['labelArrow'];
              }
          }

          arrowHead +=  ',' + color;
          labelArrowHead += ',' + color;

          if (!leftPos)
            var leftBox = rowBBox(left);
          if (!rightPos)
            var rightBox = rowBBox(right);
          var leftRow = left.chunk.row ? left.chunk.row.index : 0;
          var rightRow = right.chunk.row ? right.chunk.row.index : rows.length - 1;

          if (!arrows[arrowHead]) {
            var arrow = makeArrow(defs, arrowHead);
            if (arrow) arrows[arrowHead] = arrow;
          }
          if (!arrows[labelArrowHead]) {
            var arrow = makeArrow(defs, labelArrowHead);
            if (arrow) arrows[labelArrowHead] = arrow;
          }

          // find the next height
          var height;

          var fromIndex2, toIndex2;
          if (left.chunk.index == right.chunk.index) {
            // always in page
            fromIndex2 = left.towerId * 2 + left.chunk.row.heightsAdjust;
            toIndex2 = right.towerId * 2 + right.chunk.row.heightsAdjust;
          } else {
            // can be out of page
            var leftChunk = left.chunk.outOfPage ? firstChunk : left.chunk;
            var rightChunk = right.chunk.outOfPage ? lastChunk : right.chunk;
            fromIndex2 = left.towerId * 2 + 1 + leftChunk.row.heightsAdjust;
            toIndex2 = right.towerId * 2 - 1 + rightChunk.row.heightsAdjust;
          }
          if (!collapseArcSpace) {
            height = findArcHeight(fromIndex2, toIndex2, fragmentHeights);
            adjustFragmentHeights(fromIndex2, toIndex2, fragmentHeights, height);

            // Adjust the height to align with pixels when rendered

            // TODO: on at least Chrome, this doesn't make a difference:
            // the lines come out pixel-width even without it. Check.
            height += 0.5;
          }
          var leftSlantBound, rightSlantBound;

          var chunkReverse = false;
          var ufoCatcher = originSpan.headFragment.chunk.index == targetSpan.headFragment.chunk.index;
          if (ufoCatcher) {
            chunkReverse =
              leftBox.x + leftBox.width / 2 < rightBox.x + rightBox.width / 2;
          }
          var ufoCatcherMod = ufoCatcher ? chunkReverse ? -0.5 : 0.5 : 1;

          for (var rowIndex = leftRow; rowIndex <= rightRow; rowIndex++) {
            if (hideMidArcs && rowIndex != leftRow && rowIndex != rightRow) {
              continue;
            }

            var row = rows[rowIndex];
            if (row.chunks.length) {
              row.hasAnnotations = true;

              if (collapseArcSpace) {
                var fromIndex2R = rowIndex == leftRow ? fromIndex2 : row.heightsStart;
                var toIndex2R = rowIndex == rightRow ? toIndex2 : row.heightsEnd;
                height = findArcHeight(fromIndex2R, toIndex2R, fragmentHeights);
              }

              var arcGroup = svg.group(row.arcs, {
                  'data-from': arc.origin,
                  'data-to': arc.target
              });
              var from, to;

              if (leftBox && rowIndex == leftRow) {
                if (rtlmode) {
                  from = leftBox.x + (chunkReverse ? leftBox.width : 0);
                } else {
                  from = leftBox.x + (chunkReverse ? 0 : leftBox.width);
                }
              } else {
                from = rtlmode ? canvasWidth - 2 * Configuration.visual.margin.y - sentNumMargin : sentNumMargin;
              }

              if (rightBox && rowIndex == rightRow) {
                if (rtlmode) {
                  to = rightBox.x + (chunkReverse ? 0 : rightBox.width);
                } else {
                  to = rightBox.x + (chunkReverse ? rightBox.width : 0);
                }
              } else {
                to = rtlmode ? 0 : canvasWidth - 2 * Configuration.visual.margin.y;
              }

              if (collapseArcs) {
                var arcCacheKey = arc.type + ' ' + rowIndex + ' ' + from + ' ' + to;
                if (rowIndex == leftRow) arcCacheKey = left.span.id + ' ' + arcCacheKey;
                if (rowIndex == rightRow) arcCacheKey += ' ' + right.span.id;
                var rowHeight = arcCache[arcCacheKey];
                if (rowHeight !== undefined) {
                  height = rowHeight;
                } else {
                  arcCache[arcCacheKey] = height;
                }
              }

              if (collapseArcSpace) {
                adjustFragmentHeights(fromIndex2R, toIndex2R, fragmentHeights, height);

                // Adjust the height to align with pixels when rendered

                // TODO: on at least Chrome, this doesn't make a difference:
                // the lines come out pixel-width even without it. Check.
                height += 0.5;
              }

              var originType = data.spans[arc.origin].type;
              var arcLabels = Util.getArcLabels(spanTypes, originType, arc.type, relationTypesHash);
              var labelText = Util.arcDisplayForm(spanTypes, originType, arc.type, relationTypesHash);
              // if (Configuration.abbrevsOn && !ufoCatcher && arcLabels) {
              if (Configuration.abbrevsOn && arcLabels) {
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
              if (arc.shadowClass || arc.marked) {
                shadowGroup = svg.group(arcGroup);
              }
              var options = {
                'fill': color,
                'data-arc-role': arc.type,
                'data-arc-origin': arc.origin,
                'data-arc-target': arc.target,
                // TODO: confirm this is unused and remove.
                //'data-arc-id': arc.id,
                'data-arc-ed': arc.eventDescId,
              };

              // construct SVG text, showing possible trailing index
              // numbers (as in e.g. "Theme2") as subscripts
              var svgText;
              if (!splitArcType[2]) {
                  // no subscript, simple string suffices
                  svgText = labelText;
              } else {
                  // Need to parse out possible numeric suffixes to avoid
                  // duplicating number in label and its subscript
                  var splitLabelText = labelText.match(/^(.*?)(\d*)$/);
                  var noNumLabelText = splitLabelText[1];

                  svgText = svg.createText();
                  // TODO: to address issue #453, attaching options also
                  // to spans, not only primary text. Make sure there
                  // are no problems with this.
                  svgText.span(noNumLabelText, options);
                  var subscriptSettings = {
                    'dy': '0.3em',
                    'font-size': '80%'
                  };
                  // alternate possibility
  //                 var subscriptSettings = {
  //                   'baseline-shift': 'sub',
  //                   'font-size': '80%'
  //                 };
                  $.extend(subscriptSettings, options);
                  svgText.span(splitArcType[2], subscriptSettings);
              }

              // guess at the correct baseline shift to get vertical centering.
              // (CSS dominant-baseline can't be used as not all SVG rendereds support it.)
              var baseline_shift = sizes.arcs.height / 4;
              var text = svg.text(arcGroup, (from + to) / 2, -height + baseline_shift,
                                  svgText, options);

              var width = sizes.arcs.widths[labelText];
              var textBox = {
                x: (from + to - width) / 2,
                width: width,
                y: -height - sizes.arcs.height / 2,
                height: sizes.arcs.height,
              }
              if (arc.marked) {
                var markedRect = svg.rect(shadowGroup,
                    textBox.x - markedArcSize, textBox.y - markedArcSize,
                    textBox.width + 2 * markedArcSize, textBox.height + 2 * markedArcSize, {
                      // filter: 'url(#Gaussian_Blur)',
                      'class': "shadow_EditHighlight",
                      rx: markedArcSize,
                      ry: markedArcSize,
                });
                svg.other(markedRect, 'animate', {
                  'data-type': arc.marked,
                  attributeName: 'fill',
                  values: (arc.marked == 'match' ? highlightMatchSequence
                           : highlightArcSequence),
                  dur: highlightDuration,
                  repeatCount: 'indefinite',
                  begin: 'indefinite'
                });
              }
              if (arc.shadowClass) {
                svg.rect(shadowGroup,
                    textBox.x - arcLabelShadowSize,
                    textBox.y - arcLabelShadowSize,
                    textBox.width  + 2 * arcLabelShadowSize,
                    textBox.height + 2 * arcLabelShadowSize, {
                      'class': 'shadow_' + arc.shadowClass,
                      filter: 'url(#Gaussian_Blur)',
                      rx: arcLabelShadowRounding,
                      ry: arcLabelShadowRounding,
                });
              }
              var textStart = textBox.x;
              var textEnd = textBox.x + textBox.width;

              // adjust by margin for arc drawing
              textStart -= Configuration.visual.arcTextMargin;
              textEnd += Configuration.visual.arcTextMargin;

              if (from > to) {
                var tmp = textStart; textStart = textEnd; textEnd = tmp;
              }

              var path;

              if (roundCoordinates) {
                // don't ask
                height = (height|0)+0.5;
              }
              if (height > row.maxArcHeight) row.maxArcHeight = height;

              var myArrowHead   = ((styleMap[arcRef] && styleMap[arcRef]['arrowHead']) ||
                                   (arcDesc && arcDesc.arrowHead) ||
                                   (spanTypes.ARC_DEFAULT && spanTypes.ARC_DEFAULT.arrowHead));
              var arrowName = (symmetric ? myArrowHead || 'none' :
                    (leftToRight ? 'none' : myArrowHead || 'triangle,5')
                  ) + ',' + color;
              var arrowType = arrows[arrowName];
              var arrowDecl = arrowType && ('url(#' + arrowType + ')');

              var arrowAtLabelAdjust = 0;
              var labelArrowDecl = null;
              var myLabelArrowHead = ((styleMap[arcRef] && styleMap[arcRef]['labelArrow']) ||
                                      (arcDesc && arcDesc.labelArrow) ||
                                      (spanTypes.ARC_DEFAULT && spanTypes.ARC_DEFAULT.labelArrow));
              if (myLabelArrowHead) {
                var labelArrowName = (leftToRight ?
                    symmetric && myLabelArrowHead || 'none' :
                    myLabelArrowHead || 'triangle,5') + ',' + color;
                var labelArrowSplit = labelArrowName.split(',');
                arrowAtLabelAdjust = labelArrowSplit[0] != 'none' && parseInt(labelArrowSplit[1], 10) || 0;
                var labelArrowType = arrows[labelArrowName];
                var labelArrowDecl = labelArrowType && ('url(#' + labelArrowType + ')');
                if (ufoCatcher) arrowAtLabelAdjust = -arrowAtLabelAdjust;
              }
              var arrowStart = textStart - arrowAtLabelAdjust;
              path = svg.createPath().move(arrowStart, -height);
              if (leftBox && rowIndex == leftRow) {
                var cornerx = from + (rtlmode ? -ufoCatcherMod : ufoCatcherMod) * arcSlant;
                // for normal cases, should not be past textStart even if narrow
                if (rtlmode) {
                  if (!ufoCatcher && cornerx < arrowStart + 1) { cornerx = arrowStart + 1; }
                } else {
                  if (!ufoCatcher && cornerx > arrowStart - 1) { cornerx = arrowStart - 1; }
                }
                if (smoothArcCurves) {
                  //XXX var controlx = ufoCatcher ? cornerx + 2*ufoCatcherMod*reverseArcControlx : smoothArcSteepness*from+(1-smoothArcSteepness)*cornerx;
                  //XXX var endy = leftBox.y + (leftToRight || arc.equiv ? leftBox.height / 2 : Configuration.visual.margin.y);
                  var controlx, endy;
                  if (rtlmode) {
                    controlx = ufoCatcher ? cornerx - 2*ufoCatcherMod*reverseArcControlx : smoothArcSteepness*from+(1-smoothArcSteepness)*cornerx;
                    endy = leftBox.y + (leftToRight && !arc.equiv ? Configuration.visual.margin.y : leftBox.height / 2);
                  } else {
                    controlx = ufoCatcher ? cornerx + 2*ufoCatcherMod*reverseArcControlx : smoothArcSteepness*from+(1-smoothArcSteepness)*cornerx;
                    endy = leftBox.y + (leftToRight || arc.equiv ? leftBox.height / 2 : Configuration.visual.margin.y);
                  }
                  // no curving for short lines covering short vertical
                  // distances, the arrowheads can go off (#925)
                  if (Math.abs(-height-endy) < 2 &&
                      Math.abs(cornerx-from) < 5) {
                    endy = -height;
                  }
                  line = path.line(cornerx, -height).
                      curveQ(controlx, -height, from, endy);
                } else {
                  path.line(cornerx, -height).
                      line(from, leftBox.y + (leftToRight || arc.equiv ? leftBox.height / 2 : Configuration.visual.margin.y));
                }
              } else {
                path.line(from, -height);
              }
              svg.path(arcGroup, path, {
                  markerEnd: arrowDecl,
                  markerStart: labelArrowDecl,
                  style: 'stroke: ' + color,
                  'strokeDashArray': dashArray,
              });
              if (arc.marked) {
                svg.path(shadowGroup, path, {
                    'class': 'shadow_EditHighlight_arc',
                    strokeWidth: markedArcStroke,
                    'strokeDashArray': dashArray,
                });
                svg.other(markedRect, 'animate', {
                  'data-type': arc.marked,
                  attributeName: 'fill',
                  values: (arc.marked == 'match' ? highlightMatchSequence
                           : highlightArcSequence),
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
              if (!symmetric) {
                myArrowHead = ((arcDesc && arcDesc.arrowHead) ||
                               (spanTypes.ARC_DEFAULT && spanTypes.ARC_DEFAULT.arrowHead));
                arrowName = (leftToRight ?
                    myArrowHead || 'triangle,5' :
                    'none') + ',' + color;
              }
              var arrowType = arrows[arrowName];
              var arrowDecl = arrowType && ('url(#' + arrowType + ')');

              var arrowAtLabelAdjust = 0;
              var labelArrowDecl = null;
              var myLabelArrowHead = ((arcDesc && arcDesc.labelArrow) ||
                                      (spanTypes.ARC_DEFAULT && spanTypes.ARC_DEFAULT.labelArrow));
              if (myLabelArrowHead) {
                var labelArrowName = (leftToRight ?
                    myLabelArrowHead || 'triangle,5' :
                    symmetric && myLabelArrowHead || 'none') + ',' + color;
                var labelArrowSplit = labelArrowName.split(',');
                arrowAtLabelAdjust = labelArrowSplit[0] != 'none' && parseInt(labelArrowSplit[1], 10) || 0;
                var labelArrowType = arrows[labelArrowName];
                var labelArrowDecl = labelArrowType && ('url(#' + labelArrowType + ')');
                if (ufoCatcher) arrowAtLabelAdjust = -arrowAtLabelAdjust;
              }
              var arrowEnd = textEnd + arrowAtLabelAdjust;
              path = svg.createPath().move(arrowEnd, -height);
              if (rightBox && rowIndex == rightRow) {
                var cornerx = to - (rtlmode ? -1 : 1) * ufoCatcherMod * arcSlant;
                // TODO: duplicates above in part, make funcs
                // for normal cases, should not be past textEnd even if narrow
                if (rtlmode) {
                  if (!ufoCatcher && cornerx > arrowEnd - 1) { cornerx = arrowEnd - 1; }
                } else {
                  if (!ufoCatcher && cornerx < arrowEnd + 1) { cornerx = arrowEnd + 1; }
                }
                if (smoothArcCurves) {
                  // XXX var controlx = ufoCatcher ? cornerx - 2*ufoCatcherMod*reverseArcControlx : smoothArcSteepness*to+(1-smoothArcSteepness)*cornerx;
                  // XXX var endy = rightBox.y + (leftToRight && !arc.equiv ? Configuration.visual.margin.y : rightBox.height / 2);
                  var controlx, endy;
                  if (rtlmode) {
                    controlx = ufoCatcher ? cornerx - 2*ufoCatcherMod*reverseArcControlx : smoothArcSteepness*to+(1-smoothArcSteepness)*cornerx;
                    endy = rightBox.y + (leftToRight && !arc.equiv ? Configuration.visual.margin.y : rightBox.height / 2);
                  } else {
                    controlx = ufoCatcher ? cornerx - 2*ufoCatcherMod*reverseArcControlx : smoothArcSteepness*to+(1-smoothArcSteepness)*cornerx;
                    endy = rightBox.y + (leftToRight && !arc.equiv ? Configuration.visual.margin.y : rightBox.height / 2);
                  }
                  // no curving for short lines covering short vertical
                  // distances, the arrowheads can go off (#925)
                  if (Math.abs(-height-endy) < 2 &&
                      Math.abs(cornerx-to) < 5) {
                    endy = -height;
                  }
                  path.line(cornerx, -height).
                      curveQ(controlx, -height, to, endy);
                } else {
                  path.line(cornerx, -height).
                      line(to, rightBox.y + (leftToRight && !arc.equiv ? Configuration.visual.margin.y : rightBox.height / 2));
                }
              } else {
                path.line(to, -height);
              }
              svg.path(arcGroup, path, {
                  markerEnd: arrowDecl,
                  markerStart: labelArrowDecl,
                  style: 'stroke: ' + color,
                  'strokeDashArray': dashArray,
              });
              if (arc.marked) {
                svg.path(shadowGroup, path, {
                    'class': 'shadow_EditHighlight_arc',
                    strokeWidth: markedArcStroke,
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
            }
          } // arc rows
        }); // arcs

Util.profileEnd('arcs');
Util.profileStart('fragmentConnectors');

        $.each(data.spans, function(spanNo, span) {
          var numConnectors = span.fragments.length - 1;
          for (var connectorNo = 0; connectorNo < numConnectors; connectorNo++) {
            var left = span.fragments[connectorNo];
            var right = span.fragments[connectorNo + 1];

            if (!left.chunk.outOfPage)
              var leftBox = rowBBox(left);
            if (!right.chunk.outOfPage)
              var rightBox = rowBBox(right);
            var leftRow = left.chunk.row ? left.chunk.row.index : 0;
            var rightRow = right.chunk.row ? right.chunk.row.index : rows.length - 1;
            var box = leftBox || rightBox;
            if (!box) continue;

            for (var rowIndex = leftRow; rowIndex <= rightRow; rowIndex++) {
              var row = rows[rowIndex];
              if (row.chunks.length) {
                row.hasAnnotations = true;

                if (leftBox && rowIndex == leftRow) {
                  from = rtlmode ? leftBox.x : leftBox.x + leftBox.width;
                } else {
                  from = rtlmode ? canvasWidth - 2 * Configuration.visual.margin.y - sentNumMargin : sentNumMargin;
                }

                if (rightBox && rowIndex == rightRow) {
                  to = rtlmode ? rightBox.x + rightBox.width : rightBox.x;
                } else {
                  to = rtlmode ? 0 : canvasWidth - 2 * Configuration.visual.margin.y;
                }

                var height = box.y + box.height - Configuration.visual.margin.y;
                if (roundCoordinates) {
                  // don't ask
                  height = (height|0)+0.5;
                }

                var path = svg.createPath().move(from, height).line(to, height);
                svg.path(row.arcs, path, {
                  style: 'stroke: ' + fragmentConnectorColor,
                  'strokeDashArray': fragmentConnectorDashArray
                });
              }
            } // rowIndex
          } // connectorNo
        }); // spans

Util.profileEnd('fragmentConnectors');
Util.profileStart('rows');

        // position the rows
        var y = Configuration.visual.margin.y;
        var sentNumGroup = svg.group({'class': 'sentnum'});
        var currentSent;
        $.each(rows, function(rowId, row) {
          // find the maximum fragment height
          $.each(row.chunks, function(chunkId, chunk) {
            $.each(chunk.fragments, function(fragmentId, fragment) {
              if (row.maxSpanHeight < fragment.height) row.maxSpanHeight = fragment.height;
            });
          });
          if (row.sentence) {
            currentSent = row.sentence;
          }
          // SLOW (#724) and replaced with calculations:
          //
          // var rowBox = row.group.getBBox();
          // // Make it work on IE
          // rowBox = { x: rowBox.x, y: rowBox.y, height: rowBox.height, width: rowBox.width };
          // // Make it work on Firefox and Opera
          // if (rowBox.height == -Infinity) {
          //   rowBox = { x: 0, y: 0, height: 0, width: 0 };
          // }

          // XXX TODO HACK: find out where 5 and 1.5 come from!
          // This is the fix for #724, but the numbers are guessed.
          var rowBoxHeight = Math.max(row.maxArcHeight + 5, row.maxSpanHeight + 1.5); // XXX TODO HACK: why 5, 1.5?
          if (row.hasAnnotations) {
            // rowBox.height = -rowBox.y + rowSpacing;
            rowBoxHeight += rowSpacing + 1.5; // XXX TODO HACK: why 1.5?
          } else {
            rowBoxHeight -= 5; // XXX TODO HACK: why -5?
          }

          rowBoxHeight += rowPadding;
          var bgClass;
          if (data.markedSent[currentSent]) {
            // specifically highlighted
            bgClass = 'backgroundHighlight';
          } else if (Configuration.textBackgrounds == "striped") {
            // give every other sentence a different bg class
            bgClass = 'background'+ row.backgroundIndex;
          } else {
            // plain "standard" bg
            bgClass = 'background0';
          }
          svg.rect(backgroundGroup,
            0, y + sizes.texts.y + sizes.texts.height,
            canvasWidth, rowBoxHeight + sizes.texts.height + 1, {
            'class': bgClass,
          });
          y += rowBoxHeight;
          y += sizes.texts.height;
          row.textY = y - rowPadding;
          if (row.sentence) {
            var sentence_hash = new URLHash(coll, doc, { focus: [[ 'sent', row.sentence ]] } );
            var link = svg.link(sentNumGroup, sentence_hash.getHash());

            // Render sentence number as a link
            var text;
            if (rtlmode) {
              text = svg.text(link, canvasWidth - sentNumMargin + Configuration.visual.margin.x, y - rowPadding,
                  '' + row.sentence, { 'data-sent': row.sentence });
            } else {
              text = svg.text(link, sentNumMargin - Configuration.visual.margin.x, y - rowPadding,
                  '' + row.sentence, { 'data-sent': row.sentence });
            }

            var sentComment = data.sentComment[row.sentence];
            if (sentComment) {
              var box = text.getBBox();
              svg.remove(text);
              // TODO: using rectShadowSize, but this shadow should
              // probably have its own setting for shadow size
              shadowRect = svg.rect(link,
                  box.x - rectShadowSize, box.y - rectShadowSize,
                  box.width + 2 * rectShadowSize, box.height + 2 * rectShadowSize, {

                  'class': 'sent shadow_' + sentComment.type,
                  filter: 'url(#Gaussian_Blur)',
                  rx: rectShadowRounding,
                  ry: rectShadowRounding,
                  'data-sent': row.sentence,
              });

              // Render sentence comment
              var text;
              if (rtlmode) {
                text = svg.text(link, canvasWidth - sentNumMargin + Configuration.visual.margin.x, y - rowPadding,
                    '' + row.sentence, { 'data-sent': row.sentence }); 
              } else {
                text = svg.text(link, sentNumMargin - Configuration.visual.margin.x, y - rowPadding,
                    '' + row.sentence, { 'data-sent': row.sentence });
              }
            }
          }

          var rowY = y - rowPadding;
          if (roundCoordinates) {
            rowY = rowY|0;
          }
          translate(row, 0, rowY);
          y += Configuration.visual.margin.y;
        });
        y += Configuration.visual.margin.y;

Util.profileEnd('rows');
Util.profileStart('chunkFinish');

        // chunk index sort functions for overlapping fragment drawing
        // algorithm; first for left-to-right pass, sorting primarily
        // by start offset, second for right-to-left pass by end
        // offset. Secondary sort by fragment length in both cases.
        var currentChunk;
        var lrChunkComp = function(a,b) {
          var ac = currentChunk.fragments[a];
          var bc = currentChunk.fragments[b]
          var startDiff = Util.cmp(ac.from, bc.from);
          return startDiff != 0 ? startDiff : Util.cmp(bc.to-bc.from, ac.to-ac.from);
        }
        var rlChunkComp = function(a,b) {
          var ac = currentChunk.fragments[a];
          var bc = currentChunk.fragments[b]
          var endDiff = Util.cmp(bc.to, ac.to);
          return endDiff != 0 ? endDiff : Util.cmp(bc.to-bc.from, ac.to-ac.from);
        }

        var sentenceText = null;
        $.each(data.chunks, function(chunkNo, chunk) {
          if (chunk.outOfPage) return;

          // context for sort
          currentChunk = chunk;

          // text rendering
          if (chunk.sentence) {
            if (sentenceText) {
              // svg.text(textGroup, sentenceText); // avoids jQuerySVG bug
              svg.text(textGroup, 0, 0, sentenceText);
            }
            sentenceText = null;
          }
          if (!sentenceText) {
            sentenceText = svg.createText();
          }
          var nextChunk = data.chunks[chunkNo + 1];
          var nextSpace = nextChunk ? nextChunk.space : '';
          if (rtlmode) {
            // Render every text chunk as a SVG text so we maintain control over the layout. When 
            // rendering as a SVG span (as brat does), then the browser changes the layout on the 
            // X-axis as it likes in RTL mode.
            svg.text(textGroup, chunk.textX, chunk.row.textY, chunk.text + nextSpace, {
              'data-chunk-id': chunk.index
            });
          } else {
            // Original rendering using tspan in ltr mode as it plays nicer with selection
            sentenceText.span(chunk.text + nextSpace, {
              x: chunk.textX,
              y: chunk.row.textY,
              'data-chunk-id': chunk.index});
          }

          // chunk backgrounds
          if (chunk.fragments.length) {
            var orderedIdx = [];
            for (var i=chunk.fragments.length-1; i>=0; i--) {
              orderedIdx.push(i);
            }

            // Mark entity nesting height/depth (number of
            // nested/nesting entities). To account for crossing
            // brackets in a (mostly) reasonable way, determine
            // depth/height separately in a left-to-right traversal
            // and a right-to-left traversal.
            orderedIdx.sort(lrChunkComp);

            var openFragments = [];
            for(var i=0; i<orderedIdx.length; i++) {
              var current = chunk.fragments[orderedIdx[i]];
              current.nestingHeightLR = 0;
              current.nestingDepthLR = 0;
              var stillOpen = [];
              for(var o=0; o<openFragments.length; o++) {
                if(openFragments[o].to > current.from) {
                  stillOpen.push(openFragments[o]);
                  openFragments[o].nestingHeightLR++;
                }
              }
              openFragments = stillOpen;
              current.nestingDepthLR=openFragments.length;
              openFragments.push(current);
            }

            // re-sort for right-to-left traversal by end position
            orderedIdx.sort(rlChunkComp);

            openFragments = [];
            for(var i=0; i<orderedIdx.length; i++) {
              var current = chunk.fragments[orderedIdx[i]];
              current.nestingHeightRL = 0;
              current.nestingDepthRL = 0;
              var stillOpen = [];
              for(var o=0; o<openFragments.length; o++) {
                if(openFragments[o].from < current.to) {
                  stillOpen.push(openFragments[o]);
                  openFragments[o].nestingHeightRL++;
                }
              }
              openFragments = stillOpen;
              current.nestingDepthRL=openFragments.length;
              openFragments.push(current);
            }

            // the effective depth and height are the max of those
            // for the left-to-right and right-to-left traversals.
            for(var i=0; i<orderedIdx.length; i++) {
              var c = chunk.fragments[orderedIdx[i]];
              c.nestingHeight = c.nestingHeightLR > c.nestingHeightRL ? c.nestingHeightLR : c.nestingHeightRL;
              c.nestingDepth = c.nestingDepthLR > c.nestingDepthRL ? c.nestingDepthLR : c.nestingDepthRL;
            }

            // Re-order by nesting height and draw in order
            orderedIdx.sort(function(a,b) { return Util.cmp(chunk.fragments[b].nestingHeight, chunk.fragments[a].nestingHeight) });

            for(var i=0; i<chunk.fragments.length; i++) {
              var fragment = chunk.fragments[orderedIdx[i]];
              var spanDesc = spanTypes[fragment.span.type];
              var bgColor = ((spanDesc && spanDesc.bgColor) ||
                             (spanTypes.SPAN_DEFAULT && spanTypes.SPAN_DEFAULT.bgColor) ||
                             '#ffffff');
              if (fragment.span.hidden) continue;

              // Tweak for nesting depth/height. Recognize just three
              // levels for now: normal, nested, and nesting, where
              // nested+nesting yields normal. (Currently testing
              // minor tweak: don't shrink for depth 1 as the nesting
              // highlight will grow anyway [check nestingDepth > 1])
              var shrink = 0;
              if(fragment.nestingDepth > 1 && fragment.nestingHeight == 0) {
                  shrink = 1;
              } else if(fragment.nestingDepth == 0 && fragment.nestingHeight > 0) {
                  shrink = -1;
              }
              var yShrink = shrink * nestingAdjustYStepSize;
              var xShrink = shrink * nestingAdjustXStepSize;
              // bit lighter
              var lightBgColor = Util.adjustColorLightness(bgColor, 0.8);
              // tweak for Y start offset (and corresponding height
              // reduction): text rarely hits font max height, so this
              // tends to look better
              var yStartTweak = 1;
              // store highlight coordinates to have same mouseover highlight without recalc
              fragment.highlightPos = {
                  x: chunk.textX + (rtlmode ? (fragment.curly.from - xShrink) : (fragment.curly.from + xShrink)),
                  y: chunk.row.textY + sizes.texts.y + yShrink + yStartTweak,
                  w: fragment.curly.to - fragment.curly.from - 2*xShrink,
                  h: sizes.texts.height - 2*yShrink - yStartTweak,
              };
              svg.rect(highlightGroup,
                  fragment.highlightPos.x, fragment.highlightPos.y,
                  fragment.highlightPos.w, fragment.highlightPos.h,
                  { fill: lightBgColor, //opacity:1,
                    rx: highlightRounding.x,
                    ry: highlightRounding.y,
                  });
            }
          }
        });
        if (sentenceText) {
          // svg.text(textGroup, sentenceText); // avoids jQuerySVG bug
          svg.text(textGroup, 0, 0, sentenceText);
        }

        // draw the markedText
        $.each(textMarkedRows, function(textRowNo, textRowDesc) { // row, from, to
          var textHighlight = svg.rect(highlightGroup,
              textRowDesc[1] - 2, textRowDesc[0].textY - sizes.fragments.height,
              textRowDesc[2] - textRowDesc[1] + 4, sizes.fragments.height + 4,
              { fill: 'yellow' } // TODO: put into css file, as default - turn into class
          );
          // NOTE: changing highlightTextSequence here will give
          // different-colored highlights
          // TODO: entirely different settings for non-animations?
          var markedType = textRowDesc[3];
          svg.other(textHighlight, 'animate', {
            'data-type': markedType,
            attributeName: 'fill',
            values: (markedType == 'match' ? highlightMatchSequence
                     : highlightTextSequence),
            dur: highlightDuration,
            repeatCount: 'indefinite',
            begin: 'indefinite'
          });
        });


Util.profileEnd('chunkFinish');
Util.profileStart('finish');

        if (rtlmode) {
          svg.path(sentNumGroup, svg.createPath().
            move(canvasWidth - sentNumMargin, 0).
            line(canvasWidth - sentNumMargin, y));
        } else {
          svg.path(sentNumGroup, svg.createPath().
            move(sentNumMargin, 0).
            line(sentNumMargin, y));
        }

        // resize the SVG
        var width = maxTextWidth + sentNumMargin + 2 * Configuration.visual.margin.x + 1;
        if (width > canvasWidth) canvasWidth = width;

        $svg.width(canvasWidth);
        $svg.height(y);
        $svg.attr("viewBox", "0 0 " + canvasWidth + " " + y);
        if (rtlmode) {
          $svg.attr("direction", "rtl");
        }
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
          if (this.beginElement) { // protect against non-SMIL browsers
            this.beginElement();
          }
        });
        dispatcher.post('doneRendering', [coll, doc, args]);
      };

      var renderErrors = {
        unableToReadTextFile: true,
        annotationFileNotFound: true,
        isDirectoryError: true
      };
      var renderData = function(sourceData) {
        Util.profileEnd('invoke getDocument');
        if (sourceData && sourceData.exception) {
          if (renderErrors[sourceData.exception]) {
            dispatcher.post('renderError:' + sourceData.exception, [sourceData]);
          } else {
            dispatcher.post('unknownError', [sourceData.exception]);
          }
        } else {
          // Fill in default values that don't necessarily go over the protocol
          if (sourceData) {
            sourceData.text = Util.unicodeString(sourceData.text);
            setSourceDataDefaults(sourceData);
          }

          dispatcher.post('startedRendering', [coll, doc, args]);
          dispatcher.post('spin');
          setTimeout(function() {
              try {
                renderDataReal(sourceData);
              } catch (e) {
                // We are sure not to be drawing anymore, reset the state
                drawing = false;
                // TODO: Hook printout into dispatch elsewhere?
                console.warn('Rendering terminated due to: ' + e, e.stack);
                dispatcher.post('renderError: Fatal', [sourceData, e]);
              }
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
        if (svg && ((isRenderRequested && isCollectionLoaded) || requestedData) && Util.areFontsLoaded()) {
          isRenderRequested = false;
          if (requestedData) {

Util.profileClear();
Util.profileStart('before render');

            renderData(requestedData);
          } else if (doc.length) {

Util.profileClear();
Util.profileStart('before render');

            renderDocument();
          } else {
            dispatcher.post(0, 'renderError:noFileSpecified');
          }
        }
      };

      var requestRenderData = function(sourceData) {
        requestedData = sourceData;
        triggerRender();
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
              span.text,
              span.comment && span.comment.text,
              span.comment && span.comment.type,
              span.normalizations]);

          var spanDesc = spanTypes[span.type];
          var bgColor = ((spanDesc && spanDesc.bgColor) ||
                         (spanTypes.SPAN_DEFAULT && spanTypes.SPAN_DEFAULT.bgColor) ||
                         '#ffffff');
          if (span.hidden) return;
          highlight = [];
          $.each(span.fragments, function(fragmentNo, fragment) {
            highlight.push(svg.rect(highlightGroup,
                                 fragment.highlightPos.x, fragment.highlightPos.y,
                                 fragment.highlightPos.w, fragment.highlightPos.h,
                                 { 'fill': bgColor, opacity:0.75,
                                   rx: highlightRounding.x,
                                   ry: highlightRounding.y,
                                 }));
          });

          if (that.arcDragOrigin) {
            target.parent().addClass('highlight');
          } else {
            var equivs = {};
            var spans = {};
            spans[id] = true;
            var spanIds = [];
            // find all arcs, normal and equiv. Equivs need to go far (#1023)
            var addArcAndSpan = function(arc, span) {
              if (arc.equiv) {
                equivs[arc.eventDescId.substr(0, arc.eventDescId.indexOf('*', 2) + 1)] = true;
                var eventDesc = data.eventDescs[arc.eventDescId];
                $.each(eventDesc.leftSpans.concat(eventDesc.rightSpans), function(ospanId, ospan) {
                  spans[ospan] = true;
                });
              } else {
                spans[arc.origin] = true;
              }
            }
            $.each(span.incoming, function(arcNo, arc) {
                addArcAndSpan(arc, arc.origin);
            });
            $.each(span.outgoing, function(arcNo, arc) {
                addArcAndSpan(arc, arc.target);
            });
            var equivSelector = [];
            $.each(equivs, function(equiv, dummy) {
              equivSelector.push('[data-arc-ed^="' + equiv + '"]');
            });

            highlightArcs = $svg.
                find(equivSelector.join(', ')).
                parent().
                add('g[data-from="' + id + '"], g[data-to="' + id + '"]' + equivSelector).
                addClass('highlight');

            $.each(spans, function(spanId, dummy) {
                spanIds.push('rect[data-span-id="' + spanId + '"]');
            });
            highlightSpans = $svg.
                find(spanIds.join(', ')).
                parent().
                addClass('highlight');
          }
        } else if (!that.arcDragOrigin && (id = target.attr('data-arc-role'))) {
          var originSpanId = target.attr('data-arc-origin');
          var targetSpanId = target.attr('data-arc-target');
          var role = target.attr('data-arc-role');
          var symmetric = (relationTypesHash &&
                           relationTypesHash[role] &&
                           relationTypesHash[role].properties &&
                           relationTypesHash[role].properties.symmetric);
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
              // among arcs, only ones corresponding to relations have
              // "independent" IDs
              arcId = arcEventDescId;
            }
          }
          var originSpanType = data.spans[originSpanId].type || '';
          var targetSpanType = data.spans[targetSpanId].type || '';
          dispatcher.post('displayArcComment', [
              evt, target, symmetric, arcId,
              originSpanId, originSpanType, role,
              targetSpanId, targetSpanType,
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
        target.removeClass('badTarget');
        dispatcher.post('hideComment');
        if (highlight) {
          $.each(highlight, function() {
            svg.remove(this);
          });
          highlight = undefined;
        }
        if (highlightSpans) {
          highlightArcs.removeClass('highlight');
          highlightSpans.removeClass('highlight');
          highlightSpans = undefined;
        }
      };

      var setAbbrevs = function(_abbrevsOn) {
        // TODO: this is a slightly weird place to tweak the configuration
        Configuration.abbrevsOn = _abbrevsOn;
        dispatcher.post('configurationChanged');
      }

      var setTextBackgrounds = function(_textBackgrounds) {
        Configuration.textBackgrounds = _textBackgrounds;
        dispatcher.post('configurationChanged');
      }

      var setLayoutDensity = function(_density) {
        //dispatcher.post('messages', [[['Setting layout density ' + _density, 'comment']]]);
        // TODO: store standard settings instead of hard-coding
        // them here (again)
        if (_density < 2) {
          // dense
          Configuration.visual.margin = { x: 1, y: 0 };
          Configuration.visual.boxSpacing = 1;
          Configuration.visual.curlyHeight = 1;
          Configuration.visual.arcSpacing = 7;
          Configuration.visual.arcStartHeight = 18
        } else if(_density > 2) {
          // spacious
          Configuration.visual.margin = { x: 2, y: 1 };
          Configuration.visual.boxSpacing = 3;
          Configuration.visual.curlyHeight = 6;
          Configuration.visual.arcSpacing = 12;
          Configuration.visual.arcStartHeight = 23;
        } else {
          // standard
          Configuration.visual.margin = { x: 2, y: 1 };
          Configuration.visual.boxSpacing = 1;
          Configuration.visual.curlyHeight = 4;
          Configuration.visual.arcSpacing = 9;
          Configuration.visual.arcStartHeight = 19;
        }
        dispatcher.post('configurationChanged');
      }

      var setSvgWidth = function(_width) {
        $svgDiv.width(_width);
        if (Configuration.svgWidth != _width) {
          Configuration.svgWidth = _width;
          dispatcher.post('configurationChanged');
        }
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
          'keydown', 'keypress',
          'touchstart', 'touchend'
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

      var loadAttributeTypes = function(response_types) {
        var processed = {};
        $.each(response_types, function(aTypeNo, aType) {
          processed[aType.type] = aType;
          // count the values; if only one, it's a boolean attribute
          if (aType.values.length == 1) {
            aType.bool = aType.values[0].name;
          }
          // We need attribute values to be stored as an array, in the correct order,
          // but for efficiency of access later we also create a map of each value 
          // name to the corresponding value dictionary.
          aType.values.byName = {}
          $.each(aType.values, function(valueNo, val) {
              aType.values.byName[val.name] = val;
          });
        });
        return processed;
      }

      var loadRelationTypes = function(relation_types) {
        $.each(relation_types, function(relTypeNo, relType) {
          if (relType) {
            relationTypesHash[relType.type] = relType;
            var children = relType.children;
            if (children && children.length) {
              loadRelationTypes(children);
            }
          }
        });
      }

      var collectionLoaded = function(response) {
        if (!response.exception) {
          setCollectionDefaults(response);
          eventAttributeTypes = loadAttributeTypes(response.event_attribute_types);
          entityAttributeTypes = loadAttributeTypes(response.entity_attribute_types);
          spanTypes = {};
          loadSpanTypes(response.entity_types);
          loadSpanTypes(response.event_types);
          loadSpanTypes(response.unconfigured_types);
          relationTypesHash = {};
          loadRelationTypes(response.relation_types);
          loadRelationTypes(response.unconfigured_types);
          // TODO XXX: isn't the following completely redundant with
          // loadRelationTypes?
          $.each(response.relation_types, function(relTypeNo, relType) {
            relationTypesHash[relType.type] = relType;
          });
          var arcBundle = (response.visual_options || {}).arc_bundle || 'none';
          var textDirection = (response.visual_options || {}).text_direction || 'ltr';
          collapseArcs = arcBundle == "all";
          hideMidArcs = arcBundle == "hide";
          collapseArcSpace = arcBundle != "none";
          rtlmode = textDirection == 'rtl';

          dispatcher.post('spanAndAttributeTypesLoaded', [spanTypes, entityAttributeTypes, eventAttributeTypes, relationTypesHash]);

          isCollectionLoaded = true;
          triggerRender();
        } else {
          // exception on collection load; allow visualizer_ui
          // collectionLoaded to handle this
        }
      };

      var setPagingOffset = function(offset, rerender) {
        pagingOffset = offset;
        if (rerender) dispatcher.post('renderData', [sourceData]);
      };

      var isReloadOkay = function() {
        // do not reload while the user is in the dialog
        return !drawing;
      };

      Util.loadFonts(webFontURLs, dispatcher);

      dispatcher.
          on('collectionChanged', collectionChanged).
          on('collectionLoaded', collectionLoaded).
          on('setPagingOffset', setPagingOffset).
          on('renderData', renderData).
          on('triggerRender', triggerRender).
          on('requestRenderData', requestRenderData).
          on('isReloadOkay', isReloadOkay).
          on('resetData', resetData).
          on('abbrevs', setAbbrevs).
          on('textBackgrounds', setTextBackgrounds).
          on('layoutDensity', setLayoutDensity).
          on('svgWidth', setSvgWidth).
          on('current', gotCurrent).
          on('clearSVG', clearSVG).
          on('mouseover', onMouseOver).
          on('mouseout', onMouseOut);
    };

    return Visualizer;
})(jQuery, window);
