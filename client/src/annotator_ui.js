// -*- Mode: JavaScript; tab-width: 2; indent-tabs-mode: nil; -*-
// vim:set ft=javascript ts=2 sw=2 sts=2 cindent:
var AnnotatorUI = (function($, window, undefined) {
    var AnnotatorUI = function(dispatcher, svg) {
      var that = this;
      var arcDragOrigin = null;
      var arcDragOriginBox = null;
      var arcDragOriginGroup = null;
      var arcDragArc = null;
      var arcDragJustStarted = false;
      var sourceData = null;
      var data = null;
      var searchConfig = null;
      var spanOptions = null;
      var lockOptions = null;
      var rapidSpanOptions = null;
      var arcOptions = null;
      var spanKeymap = null;
      var keymap = null;
      var coll = null;
      var doc = null;
      var reselectedSpan = null;
      var selectedFragment = null;
      var editedSpan = null;
      var editedFragment = null;
      var repeatingArcTypes = [];
      var spanTypes = null;
      var entityAttributeTypes = null;
      var eventAttributeTypes = null;
      var relationTypesHash = null;
      var showValidAttributes; // callback function
      var showValidNormalizations; // callback function
      var dragStartedAt = null;
      var selRect = null;
      var lastStartRec = null;
      var lastEndRec = null;
      var inForm = false;
      var normalizations = {};

      var draggedArcHeight = 30;
      var maxNormSearchHistory = 10;

      // TODO: this is an ugly hack, remove (see comment with assignment)
      var lastRapidAnnotationEvent = null;
      // TODO: another avoidable global; try to work without
      var rapidAnnotationDialogVisible = false;

      // amount by which to lighten (adjust "L" in HSL space) span
      // colors for type selection box BG display. 0=no lightening,
      // 1=white BG (no color)
      var spanBoxTextBgColorLighten = 0.4;

      // for double-click selection simulation hack
      var lastDoubleClickedChunkId = null;

      // for normalization: URLs bases by norm DB name
      var normDbUrlByDbName = {};
      var normDbUrlBaseByDbName = {};
      // for normalization: appropriate DBs per type
      var normDbsByType = {};
      // for normalization
      var oldSpanNormIdValue = '';
      var lastNormSearches = [];

      that.user = null;
      var svgElement = $(svg._svg);
      var svgId = svgElement.parent().attr('id');

      var arcTargets = [];
      var arcTargetRects;

      var stripNumericSuffix = function(s) {
        // utility function, originally for stripping numerix suffixes
        // from arc types (e.g. "Theme2" -> "Theme"). For values
        // without suffixes (including non-strings), returns given value.
        if (typeof(s) != "string") {          
          return s; // can't strip
        }
        var m = s.match(/^(.*?)(\d*)$/);
        return m[1]; // always matches
      }

      var showForm = function() {
        inForm = true;
      };

      var hideForm = function() {
        inForm = false;
        keymap = null;
        rapidAnnotationDialogVisible = false;
      };

      var clearSelection = function() {
        window.getSelection().removeAllRanges();
        if (selRect != null) {
          for(var s=0; s != selRect.length; s++) {
            selRect[s].parentNode.removeChild(selRect[s]);
          }
          selRect = null;
          lastStartRec = null;
          lastEndRec = null;
        }
      };

      var makeSelRect = function(rx, ry, rw, rh, col) {
        var selRect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        selRect.setAttributeNS(null, "width", rw);
        selRect.setAttributeNS(null, "height", rh);
        selRect.setAttributeNS(null, "x", rx);
        selRect.setAttributeNS(null, "y", ry);
        selRect.setAttributeNS(null, "fill", col == undefined ? "lightblue" : col);
        return selRect;
      };

      var onKeyDown = function(evt) {
        var code = evt.which;

        if (code === $.ui.keyCode.ESCAPE) {
          setTypeLock(false);
          stopArcDrag();
          hideForm();
          if (reselectedSpan) {
            $(reselectedSpan.rect).removeClass('reselect');
            reselectedSpan = null;
            svgElement.removeClass('reselect');
          }
          return;
        }

        // in rapid annotation mode, prioritize the keys 0..9 for the
        // ordered choices in the quick annotation dialog.
        if (Configuration.rapidModeOn && rapidAnnotationDialogVisible && 
            "0".charCodeAt() <= code && code <= "9".charCodeAt()) {
          var idx = String.fromCharCode(code);
          var $input = $('#rapid_span_'+idx);
          if ($input.length) {
            $input.click();
          }
        }

        if (!inForm && code == $.ui.keyCode.ENTER) {
          evt.preventDefault();
          tryToAnnotate(evt);
          return;
        }


        // disable shortcuts when working with elements that you could
        // conceivably type in
        var target = evt.target;
        var nodeName = target.nodeName.toLowerCase();
        var nodeType = target.type && target.type.toLowerCase();
        if (nodeName == 'input' && (nodeType == 'text' || nodeType == 'password')) return;
        if (nodeName == 'textarea' || nodeName == 'select') return;

        var prefix = '';
        if (Util.isMac ? evt.metaKey : evt.ctrlKey) {
          prefix += "C-";
        }
        if (evt.altKey) {
          prefix += "A-";
        }
        if (evt.shiftKey) {
          prefix += "S-";
        }
        var key = String.fromCharCode(code);

        // repeat last action on the match focus (the current search result)
        if (prefix + key == 'C-H') {
          if (args.matchfocus) {
            var valency = args.matchfocus[0].length;
            if (valency == 2) { // text offsets
              if (spanOptions) { // previous span edit exists
                if (spanOptions.action == 'createSpan' && !spanOptions.id) {
                  // new
                  spanOptions.offsets = args.matchfocus;
                  spanFormSubmit();
                  dispatcher.post('logAction', ['spanSearchCreated']);
                } else {
                  // edit
                  var spanId = Object.keys(data.spans).find(function(spanId) {
                    return Util.isEqual(data.spans[spanId].offsets, args.matchfocus);
                  });
                  if (spanId) {
                    spanOptions.id = spanId;
                    var span = data.spans[spanId];
                    if (spanOptions.action == 'deleteSpan') {
                      spanOptions.type = span.type;
                      deleteSpan();
                      dispatcher.post('logAction', ['spanSearchDeleted']);
                    } else if (spanOptions.action == 'createSpan') {
                      // modify: type, attributes, normalizations, comment
                      spanOptions.offsets = span.offsets;
                      spanFormSubmit();
                      dispatcher.post('logAction', ['spanSearchModified']);
                    } else {
                      //TODO
                      console.log("Not implemented yet");
                    }
                  }
                }
              } else { // no previous span edit, so bring up the dialog
                var spanText = data.text.substring(args.matchfocus[0][0], args.matchfocus[0][1]);
                spanOptions = {
                  action: 'createSpan',
                  offsets: args.matchfocus
                }
                fillSpanTypesAndDisplayForm(evt, spanText, null);
                // for precise timing, log annotation display to user.
                dispatcher.post('logAction', ['spanSearchSelected']);
              }
            } else if (valency == 1) { // span ID
              let spanId = args.matchfocus[0][0];
            } else if (valency == 3) { // relationship; XXX TODO not sure what to do with this
            }
          }
          evt.preventDefault();
          return false;
        }

        if (!keymap) return;

        var binding = keymap[prefix + code] || keymap[prefix + key];
        if (binding) {
          var boundInput = $('#' + binding)[0];
          if (boundInput && !boundInput.disabled) {
            boundInput.click();
            evt.preventDefault();
            return false;
          }
        }
      };

      var onDblClick = function(evt) {
        // must be logged in
        if (that.user === null) return;
        // must not be reselecting a span or an arc
        if (reselectedSpan || arcDragOrigin) return;

        var target = $(evt.target);
        var id;

        // do we edit an arc?
        if (id = target.attr('data-arc-role')) {
          // TODO
          clearSelection();
          var originSpanId = target.attr('data-arc-origin');
          var targetSpanId = target.attr('data-arc-target');
          var type = target.attr('data-arc-role');
          var originSpan = data.spans[originSpanId];
          var targetSpan = data.spans[targetSpanId];
          arcOptions = {
            action: 'createArc',
            origin: originSpanId,
            target: targetSpanId,
            old_target: targetSpanId,
            type: type,
            old_type: type,
            collection: coll,
            'document': doc
          };
          var eventDescId = target.attr('data-arc-ed');
          if (eventDescId) {
            var eventDesc = data.eventDescs[eventDescId];
            arcOptions.id = eventDescId;
            arcOptions.comment = eventDesc.comment && eventDesc.comment.text;
            if (eventDesc.equiv) {
              arcOptions['left'] = eventDesc.leftSpans.join(',');
              arcOptions['right'] = eventDesc.rightSpans.join(',');
            }
          } else {
            arcOptions.id = originSpanId + "~" + type + "~" + targetSpanId;
          }
          $('#arc_origin').text(Util.spanDisplayForm(spanTypes, originSpan.type) + ' ("' + originSpan.text + '")');
          $('#arc_target').text(Util.spanDisplayForm(spanTypes, targetSpan.type) + ' ("' + targetSpan.text + '")');
          var arcId = eventDescId || [originSpanId, type, targetSpanId];
          fillArcTypesAndDisplayForm(evt, originSpan.type, targetSpan.type, type, arcId);
          // for precise timing, log dialog display to user.
          dispatcher.post('logAction', ['arcEditSelected']);

        // if not an arc, then do we edit a span?
        } else if (id = target.attr('data-span-id')) {
          clearSelection();
          editedSpan = data.spans[id];
          editedFragment = target.attr('data-fragment-id');
          // XXX we went from collecting fragment offsets to copying
          // them from data. Does anything break?
          spanOptions = {
            action: 'createSpan',
            offsets: editedSpan.unsegmentedOffsets,
            type: editedSpan.type,
            id: id,
          };
          if (lockOptions) {
            spanFormSubmit();
            dispatcher.post('logAction', ['spanLockEditSubmitted']);
          } else {
            fillSpanTypesAndDisplayForm(evt, editedSpan.text, editedSpan);
            // for precise timing, log annotation display to user.
            dispatcher.post('logAction', ['spanEditSelected']);
          }
        }

        // if not an arc or a span, is this a double-click on text?
        else if (id = target.attr('data-chunk-id')) {
          // remember what was clicked (this is in preparation for
          // simulating double-click selection on browsers that do
          // not support it.
          lastDoubleClickedChunkId = id;
        }
      };

      var startArcDrag = function(originId) {
        if (reselectedSpan) return;
        clearSelection();
        svgPosition = svgElement.offset();
        svgElement.addClass('unselectable');
        arcDragOrigin = originId;
        arcDragOriginGroup = $(data.spans[arcDragOrigin].group);
        arcDragOriginGroup.addClass('highlight');
        var headFragment = data.spans[arcDragOrigin].headFragment;
        var chunk = headFragment.chunk;
        var fragBox = headFragment.rectBox;
        arcDragOriginBox = {
            x: fragBox.x + chunk.translation.x,
            y: fragBox.y + chunk.row.translation.y,
            height: fragBox.height,
            width: fragBox.width,
            center: fragBox.x + chunk.translation.x + fragBox.width / 2,
          };

        arcDragJustStarted = true;
      };

      var getValidArcTypesForDrag = function(targetId, targetType) {
        var arcType = stripNumericSuffix(arcOptions && arcOptions.type);
        if (!arcDragOrigin || targetId == arcDragOrigin) return null;

        var originType = data.spans[arcDragOrigin].type;
        var spanType = spanTypes[originType];
        var result = [];
        if (spanType && spanType.arcs) {
          $.each(spanType.arcs, function(arcNo, arc) {
            if (arcType && arcType != arc.type) return;

            if ($.inArray(targetType, arc.targets) != -1) {
              result.push(arc.type);
            }
          });
        }
        return result;
      };

      var onMouseDown = function(evt) {
        dragStartedAt = evt; // XXX do we really need the whole evt?
        if (!that.user || arcDragOrigin) return;
        var target = $(evt.target);
        var id;
        // is it arc drag start?
        if (id = target.attr('data-span-id')) {
          arcOptions = null;
          startArcDrag(id);
          evt.stopPropagation();
          evt.preventDefault();
          return false;
        }
      };

      var onMouseMove = function(evt) {
        if (arcDragOrigin) {
          if (arcDragJustStarted) {
            arcDragArc.setAttribute('visibility', 'visible');
            // show the possible targets
            var span = data.spans[arcDragOrigin] || {};
            var spanDesc = spanTypes[span.type] || {};

            // separate out possible numeric suffix from type for highight
            // (instead of e.g. "Theme3", need to look for "Theme")
            var noNumArcType = stripNumericSuffix(arcOptions && arcOptions.type);
            var targetTypes = [];
            $.each(spanDesc.arcs || [], function(possibleArcNo, possibleArc) {
              if ((arcOptions && possibleArc.type == noNumArcType) || !(arcOptions && arcOptions.old_target)) {
                $.each(possibleArc.targets || [], function(possibleTargetNo, possibleTarget) {
                  targetTypes.push(possibleTarget);
                });
              }
            });
            arcTargets = [];
            arcTargetRects = [];
            $.each(data.spans, function(spanNo, span) {
              if (span.id == arcDragOrigin) return;
              if (targetTypes.indexOf(span.type) != -1) {
                arcTargets.push(span.id);
                $.each(span.fragments, function(fragmentNo, fragment) {
                  arcTargetRects.push(fragment.rect);
                });
              }
            });
            $(arcTargetRects).addClass('reselectTarget');
          }
          clearSelection();
          var mx = evt.pageX - svgPosition.left;
          var my = evt.pageY - svgPosition.top + 5; // TODO FIXME why +5?!?
          var y = Math.min(arcDragOriginBox.y, my) - draggedArcHeight;
          var dx = (arcDragOriginBox.center - mx) / 4;
          var path = svg.createPath().
            move(arcDragOriginBox.center, arcDragOriginBox.y).
            curveC(arcDragOriginBox.center - dx, y,
                mx + dx, y,
                mx, my);
          arcDragArc.setAttribute('d', path.path());
        } else {
          // A. Scerri FireFox chunk

          // if not, then is it span selection? (ctrl key cancels)
          var sel = window.getSelection();
          var chunkIndexFrom = sel.anchorNode && $(sel.anchorNode.parentNode).attr('data-chunk-id');
          var chunkIndexTo = sel.focusNode && $(sel.focusNode.parentNode).attr('data-chunk-id');
          // fallback for firefox (at least):
          // it's unclear why, but for firefox the anchor and focus
          // node parents are always undefined, the the anchor and
          // focus nodes themselves do (often) have the necessary
          // chunk ID. However, anchor offsets are almost always
          // wrong, so we'll just make a guess at what the user might
          // be interested in tagging instead of using what's given.
          var anchorOffset = null;
          var focusOffset = null;
          if (chunkIndexFrom === undefined && chunkIndexTo === undefined &&
              $(sel.anchorNode).attr('data-chunk-id') &&
              $(sel.focusNode).attr('data-chunk-id')) {
            // Lets take the actual selection range and work with that
            // Note for visual line up and more accurate positions a vertical offset of 8 and horizontal of 2 has been used!
            var range = sel.getRangeAt(0);
            var svgOffset = $(svg._svg).offset();
            var flip = false;
            var tries = 0;
            // First try and match the start offset with a position, if not try it against the other end
            while (tries < 2) {
              var sp = svg._svg.createSVGPoint();
              sp.x = (flip ? evt.pageX : dragStartedAt.pageX) - svgOffset.left;
              sp.y = (flip ? evt.pageY : dragStartedAt.pageY) - (svgOffset.top + 8);
              var startsAt = range.startContainer;
              anchorOffset = startsAt.getCharNumAtPosition(sp);
              chunkIndexFrom = startsAt && $(startsAt).attr('data-chunk-id');
              if (anchorOffset != -1) {
                break;
              }
              flip = true;
              tries++;
            }

            // Now grab the end offset
            sp.x = (flip ? dragStartedAt.pageX : evt.pageX) - svgOffset.left;
            sp.y = (flip ? dragStartedAt.pageY : evt.pageY) - (svgOffset.top + 8);
            var endsAt = range.endContainer;
            focusOffset = endsAt.getCharNumAtPosition(sp);

            // If we cannot get a start and end offset stop here
            if (anchorOffset == -1 || focusOffset == -1) {
              return;
            }
            // If we are in the same container it does the selection back to front when dragged right to left, across different containers the start is the start and the end if the end!
            if(range.startContainer == range.endContainer && anchorOffset > focusOffset) {
              var t = anchorOffset;
              anchorOffset = focusOffset;
              focusOffset = t;
              flip = false;
            }
            chunkIndexTo = endsAt && $(endsAt).attr('data-chunk-id');

            // Now take the start and end character rectangles
            startRec = startsAt.getExtentOfChar(anchorOffset);
            startRec.y += 2;
            endRec = endsAt.getExtentOfChar(focusOffset);
            endRec.y += 2;

            // If nothing has changed then stop here
            if (lastStartRec != null && lastStartRec.x == startRec.x && lastStartRec.y == startRec.y && lastEndRec != null && lastEndRec.x == endRec.x && lastEndRec.y == endRec.y) {
              return;
            }

            if (selRect == null) {
              var rx = startRec.x;
              var ry = startRec.y;
              var rw = (endRec.x + endRec.width) - startRec.x;
              if (rw < 0) {
                rx += rw;
                rw = -rw;
              }
              var rh = Math.max(startRec.height, endRec.height);

              selRect = new Array();
              var activeSelRect = makeSelRect(rx, ry, rw, rh);
              selRect.push(activeSelRect);
              startsAt.parentNode.parentNode.parentNode.insertBefore(activeSelRect, startsAt.parentNode.parentNode);
            } else {
              if (startRec.x != lastStartRec.x && endRec.x != lastEndRec.x && (startRec.y != lastStartRec.y || endRec.y != lastEndRec.y)) {
                if (startRec.y < lastStartRec.y) {
                  selRect[0].setAttributeNS(null, "width", lastStartRec.width);
                  lastEndRec = lastStartRec;
                } else if (endRec.y > lastEndRec.y) {
                  selRect[selRect.length - 1].setAttributeNS(null, "x",
                      parseFloat(selRect[selRect.length - 1].getAttributeNS(null, "x"))
                      + parseFloat(selRect[selRect.length - 1].getAttributeNS(null, "width"))
                      - lastEndRec.width);
                  selRect[selRect.length - 1].setAttributeNS(null, "width", 0);
                  lastStartRec=lastEndRec;
                }
              }

              // Start has moved
              var flip = !(startRec.x == lastStartRec.x && startRec.y == lastStartRec.y);
              // If the height of the start or end changed we need to check whether
              // to remove multi line highlights no longer needed if the user went back towards their start line
              // and whether to create new ones if we moved to a newline
              if (((endRec.y != lastEndRec.y)) || ((startRec.y != lastStartRec.y))) {
                // First check if we have to remove the first highlights because we are moving towards the end on a different line
                var ss = 0;
                for (; ss != selRect.length; ss++) {
                  if (startRec.y <= parseFloat(selRect[ss].getAttributeNS(null, "y"))) {
                    break;
                  }
                }
                // Next check for any end highlights if we are moving towards the start on a different line
                var es = selRect.length - 1;
                for (; es != -1; es--) {
                  if (endRec.y >= parseFloat(selRect[es].getAttributeNS(null, "y"))) {
                    break;
                  }
                }
                // TODO put this in loops above, for efficiency the array slicing could be done separate still in single call
                var trunc = false;
                if (ss < selRect.length) {
                  for (var s2 = 0; s2 != ss; s2++) {
                    selRect[s2].parentNode.removeChild(selRect[s2]);
                    es--;
                    trunc = true;
                  }
                  selRect = selRect.slice(ss);
                }
                if (es > -1) {
                  for (var s2 = selRect.length - 1; s2 != es; s2--) {
                    selRect[s2].parentNode.removeChild(selRect[s2]);
                    trunc = true;
                  }
                  selRect = selRect.slice(0, es + 1);
                }

                // If we have truncated the highlights we need to readjust the last one
                if (trunc) {
                  var activeSelRect = flip ? selRect[0] : selRect[selRect.length - 1];
                  if (flip) {
                    var rw = 0;
                    if (startRec.y == endRec.y) {
                      rw = (endRec.x + endRec.width) - startRec.x;
                    } else {
                      rw = (parseFloat(activeSelRect.getAttributeNS(null, "x"))
                          + parseFloat(activeSelRect.getAttributeNS(null, "width")))
                          - startRec.x;
                    }
                    activeSelRect.setAttributeNS(null, "x", startRec.x);
                    activeSelRect.setAttributeNS(null, "y", startRec.y);
                    activeSelRect.setAttributeNS(null, "width", rw);
                  } else {
                    var rw = (endRec.x + endRec.width) - parseFloat(activeSelRect.getAttributeNS(null, "x"));
                    activeSelRect.setAttributeNS(null, "width", rw);
                  }
                } else {
                  // We didnt truncate anything but we have moved to a new line so we need to create a new highlight
                  var lastSel = flip ? selRect[0] : selRect[selRect.length - 1];
                  var startBox = startsAt.parentNode.getBBox();
                  var endBox = endsAt.parentNode.getBBox();

                  if (flip) {
                    lastSel.setAttributeNS(null, "width",
                        (parseFloat(lastSel.getAttributeNS(null, "x"))
                        + parseFloat(lastSel.getAttributeNS(null, "width")))
                        - endBox.x);
                    lastSel.setAttributeNS(null, "x", endBox.x);
                  } else {
                    lastSel.setAttributeNS(null, "width",
                        (startBox.x + startBox.width)
                        - parseFloat(lastSel.getAttributeNS(null, "x")));
                  }
                  var rx = 0;
                  var ry = 0;
                  var rw = 0;
                  var rh = 0;
                  if (flip) {
                    rx = startRec.x;
                    ry = startRec.y;
                    rw = $(svg._svg).width() - startRec.x;
                    rh = startRec.height;
                  } else {
                    rx = endBox.x;
                    ry = endRec.y;
                    rw = (endRec.x + endRec.width) - endBox.x;
                    rh = endRec.height;
                  }
                  var newRect = makeSelRect(rx, ry, rw, rh);
                  if (flip) {
                    selRect.unshift(newRect);
                  } else {
                    selRect.push(newRect);
                  }

                  // Place new highlight in appropriate slot in SVG graph
                  startsAt.parentNode.parentNode.parentNode.insertBefore(newRect, startsAt.parentNode.parentNode);
                }
              } else {
                // The user simply moved left or right along the same line so just adjust the current highlight
                var activeSelRect = flip ? selRect[0] : selRect[selRect.length - 1];
                // If the start moved shift the highlight and adjust width
                if (flip) {
                  var rw = (parseFloat(activeSelRect.getAttributeNS(null, "x"))
                      + parseFloat(activeSelRect.getAttributeNS(null, "width")))
                      - startRec.x;
                  activeSelRect.setAttributeNS(null, "x", startRec.x);
                  activeSelRect.setAttributeNS(null, "y", startRec.y);
                  activeSelRect.setAttributeNS(null, "width", rw);
                } else {
                  // If the end moved then simple change the width
                  var rw = (endRec.x + endRec.width)
                      - parseFloat(activeSelRect.getAttributeNS(null, "x"));
                  activeSelRect.setAttributeNS(null, "width", rw);
                }
              }
            }
            lastStartRec = startRec;
            lastEndRec = endRec;
          }
        }
        arcDragJustStarted = false;
      };

      var adjustToCursor = function(evt, element, centerX, centerY) {
        var screenHeight = $(window).height() - 8; // TODO HACK - no idea why -8 is needed
        var screenWidth = $(window).width() - 8;
        var elementHeight = element.height();
        var elementWidth = element.width();
        var cssSettings = {};
        var eLeft;
        var eTop;
        if (centerX) {
            eLeft = evt.clientX - elementWidth/2;
        } else {
            eLeft = evt.clientX;
        }
        if (centerY) {
            eTop = evt.clientY - elementHeight/2;
        } else {
            eTop = evt.clientY;
        }
        // Try to make sure the element doesn't go off-screen.
        // If this isn't possible (the element is larger than the screen),
        // alight top-left corner of screen and dialog as a compromise.
        if (screenWidth > elementWidth) {
            eLeft = Math.min(Math.max(eLeft,0), screenWidth - elementWidth);
        } else {
            eLeft = 0;
        } 
        if (screenHeight > elementHeight) {
            eTop  = Math.min(Math.max(eTop,0), screenHeight - elementHeight);
        } else {
            eTop  = 0;
        }
        element.css({ top: eTop, left: eLeft });
      };

      var updateCheckbox = function($input) {
        var $widget = $input.button('widget');
        var $textspan = $widget.find('.ui-button-text');
        $textspan.html(($input[0].checked ? '&#x2611; ' : '&#x2610; ') + $widget.attr('data-bare'));
      };

      var fillSpanTypesAndDisplayForm = function(evt, spanText, span) {
        keymap = spanKeymap;

        // Figure out whether we should show or hide one of the two
        // main halves of the selection frame (entities / events).
        // This depends on the type of the current span, if any, and
        // the availability of types to select.
        var hideFrame;
        if (span) {
          // existing span; only show relevant half
          if (span.generalType == 'entity') {
            hideFrame = 'event';
          } else {
            hideFrame = 'entity';
          }
          spanForm.dialog('option', { title: 'Edit Annotation' });
        } else {
          // new span; show everything that's available
          if ($('#event_types').find('input').length == 0) {
            hideFrame = 'event';
          } else if ($('#entity_types').find('input').length == 0) {
            hideFrame = 'entity';
          } else {
            hideFrame = 'none';
          }
          spanForm.dialog('option', { title: 'New Annotation' });
        }
        if (hideFrame == 'event') {
          $('#span_event_section').hide()
          $('#span_entity_section').show().
            removeClass('wrapper_half_left').
            addClass('wrapper_full_width');
        } else if (hideFrame == 'entity') {
          $('#span_entity_section').hide()
          $('#span_event_section').show().
            removeClass('wrapper_half_right').
            addClass('wrapper_full_width');
        } else {
          // show both entity and event halves
          $('#span_entity_section').show().
            removeClass('wrapper_full_width').
            addClass('wrapper_half_left');
          $('#span_event_section').show().
            removeClass('wrapper_full_width').
            addClass('wrapper_half_right');
        }

        // only show "delete" button if there's an existing annotation to delete
        if (span) {
          $('#del_span_button').show();
        } else {
          $('#del_span_button').hide();
        }

        $('#span_selected').text(spanText);
        var encodedText = encodeURIComponent(spanText);       
        $.each(searchConfig, function(searchNo, search) {
          $('#span_'+search[0]).attr('href', search[1].replace('%s', encodedText));
        });

        // enable all inputs by default (see setSpanTypeSelectability)
        $('#span_form input:not([unused])').removeAttr('disabled');

        // close span types if there's over typeCollapseLimit
        if ($('#entity_types .item').length > Configuration.typeCollapseLimit) {
          $('#entity_types .open').removeClass('open');
        }
        if ($('#event_types .item').length > Configuration.typeCollapseLimit) {
          $('#event_types .open').removeClass('open');
        }

        var showAllAttributes = false;
        if (span) {
          var linkHash = new URLHash(coll, doc, { focus: [[span.id]] }).getHash();
          var el = $('#span_' + span.type);
          if (el.length) {
            el[0].checked = true;
          } else {
            $('#span_form input:radio:checked').each(function (radioNo, radio) {
              radio.checked = false;
            });
          }

          // open the span type
          $('#span_' + span.type).parents('.collapsible').each(function() {
            toggleCollapsible($(this).parent().prev(), true);
          });

          // count the repeating arc types
          var arcTypeCount = {};
          repeatingArcTypes = [];
          $.each(span.outgoing, function(arcNo, arc) {
            // parse out possible number suffixes to allow e.g. splitting
            // on "Theme" for args ("Theme1", "Theme2").
            var splitArcType = arc.type.match(/^(.*?)(\d*)$/);
            var noNumArcType = splitArcType[1];
            if ((arcTypeCount[noNumArcType] = (arcTypeCount[noNumArcType] || 0) + 1) == 2) {
              repeatingArcTypes.push(noNumArcType);
            }
          });
          if (repeatingArcTypes.length) {
            $('#span_form_split').show();
          } else {
            $('#span_form_split').hide();
          }
        } else {
          var offsets = spanOptions.offsets[0];
          var linkHash = new URLHash(coll, doc, { focus: [[offsets[0], offsets[1]]] }).getHash();
          var firstRadio = $('#span_form input:radio:not([unused]):first')[0];
          if (firstRadio) {
            firstRadio.checked = true;
          } else {
            dispatcher.post('hideForm');
            dispatcher.post('messages', [[['No valid span types defined', 'error']]]);
            return;
          }
          $('#span_form_split').hide();
          $('#span_notes').val('');
          showAllAttributes = true;
        }
        $('#span_highlight_link').attr('href', linkHash);
        if (span && !reselectedSpan) {
          $('#span_form_reselect, #span_form_delete, #span_form_add_fragment').show();
          keymap[$.ui.keyCode.DELETE] = 'span_form_delete';
          keymap[$.ui.keyCode.INSERT] = 'span_form_reselect';
          keymap['S-' + $.ui.keyCode.ENTER] = 'span_form_add_fragment';
          $('#span_notes').val(span.annotatorNotes || '');
        } else {
          $('#span_form_reselect, #span_form_delete, #span_form_add_fragment').hide();
          keymap[$.ui.keyCode.DELETE] = null;
          keymap[$.ui.keyCode.INSERT] = null;
          keymap['S-' + $.ui.keyCode.ENTER] = null;
        }
        if (span && !reselectedSpan && span.offsets.length > 1) {
          $('#span_form_reselect_fragment, #span_form_delete_fragment').show();
          keymap['S-' + $.ui.keyCode.DELETE] = 'span_form_delete_fragment';
          keymap['S-' + $.ui.keyCode.INSERT] = 'span_form_reselect_fragment';
        } else {
          $('#span_form_reselect_fragment, #span_form_delete_fragment').hide();
          keymap['S-' + $.ui.keyCode.DELETE] = null;
          keymap['S-' + $.ui.keyCode.INSERT] = null;
        }
        // TODO: lots of redundancy in the next two blocks, clean up
        if (!span) {
          // no existing annotation, reset attributes
          var attrCategoryAndTypes = [['entity', entityAttributeTypes],
                                      ['event', eventAttributeTypes]];
          $.each(attrCategoryAndTypes, function(ctNo, ct) {
            var category = ct[0];
            var attributeTypes = ct[1];
            $.each(attributeTypes, function(attrNo, attr) {
              $input = $('#'+category+'_attr_'+Util.escapeQuotes(attr.type));
              if (attr.unused) {
                $input.val('');
              } else if (attr.default) {
                  if (attr.bool) {
                    // take any non-empty default value as "true"
                    $input[0].checked = true;
                    updateCheckbox($input);
                    $input.button('refresh');
                  } else {
                    $input.val(attr.default).change();
                  }
              } else if (attr.bool) {
                $input[0].checked = false;
                updateCheckbox($input);
                $input.button('refresh');
              } else {
                $input.val('').change();
              }
            });
          });
        } else if (!reselectedSpan) {
          // existing annotation, fill attribute values from span
          var attributeTypes;
          var category;
          if (span.generalType == 'entity') {
            attributeTypes = entityAttributeTypes;
            category = 'entity';
          } else if (span.generalType == 'trigger') {
            attributeTypes = eventAttributeTypes;
            // TODO: unify category/generalType values ('trigger' vs. 'event')
            category = 'event';
          } else {
            console.error('Unrecognized generalType:', span.generalType);
          }
          $.each(attributeTypes, function(attrNo, attr) {
            $input = $('#'+category+'_attr_'+Util.escapeQuotes(attr.type));
            var val = span.attributes[attr.type];
            if (attr.unused) {
              $input.val(val || '');
            } else if (attr.bool) {
              $input[0].checked = val;
              updateCheckbox($input);
              $input.button('refresh');
            } else {
              $input.val(val || '').change();
            }
          });
        }

        var showValidNormalizationsFor = function(type) {
          // set DB selector to the first appropriate for the type.
          // TODO: actually disable inappropriate ones.
          // TODO: support specific IDs, not just DB specifiers
          var firstDb = type && normDbsByType[type] ? normDbsByType[type][0] : null;
          if (firstDb) {
            $('#span_norm_db').val(firstDb);
          }
        }

        showValidNormalizations = function() {
          // set norm DB selector according to the first selected type
          var firstSelected = $('#entity_and_event_wrapper input:radio:checked')[0];
          var selectedType = firstSelected ? firstSelected.value : null;
          showValidNormalizationsFor(selectedType);
        }

        // fill normalizations (if any)
        if (!reselectedSpan) {
          // clear first
          clearNormalizationUI();

          var $normDb = $('#span_norm_db');
          var $normId = $('#span_norm_id');
          var $normText = $('#span_norm_txt');

          // fill if found (NOTE: only shows last on multiple)
          var normFilled = false;
          normalizations = {};
          $.each(span ? span.normalizations : [], function(normNo, norm) {
            var refDb = norm[0], refId = norm[1], refText = norm[2];
            $normDb.val(refDb);
            // could the DB selector be set? (i.e. is refDb configured?)
            if ($normDb.val() == refDb) {
              if (!normFilled) normFilled = refDb;
              if (!normalizations[refDb]) normalizations[refDb] = []
              normalizations[refDb].push([refId, refText]);
            } else {
              // can't set the DB selector; assume DB is not configured,
              // warn and leave blank (will remove norm when dialog is OK'd)
              dispatcher.post('messages', [[['Warning: '+refDb+' not configured, removing normalization.', 'warning']]]);
            }
          });
          if (normFilled) {
            // DB is OK, set the rest also
            var norm = normalizations[normFilled][0];
            oldSpanNormIdValue = norm[0];
            $normId.val(norm[0]);
            $normText.val(norm[1]);
            // TODO: check if ID is valid
            console.log(normalizations, normFilled);
            $normId.attr('data-value', normalizations[normFilled].length == 1 ? 'valid' : 'multi')
          } else {
            // if there is no existing normalization, show valid ones
            showValidNormalizations();
          }

          // update links
          updateNormalizationRefLink();
          updateNormalizationDbLink();
        }

        var showAttributesFor = function(attrTypes, category, type) {
          var validAttrs = type ? spanTypes[type].attributes : [];
          var shownCount = 0;
          $.each(attrTypes, function(attrNo, attr) {
            var $input = $('#'+category+'_attr_'+Util.escapeQuotes(attr.type));
            var showAttr = showAllAttributes || $.inArray(attr.type, validAttrs) != -1;
            if (showAttr) {
              // $input.button('widget').parent().show();
              $input.closest('.attribute_type_label').show();
              shownCount++;
            } else {
              // $input.button('widget').parent().hide();
              $input.closest('.attribute_type_label').hide();
            }
          });
          return shownCount;
        }

        showValidAttributes = function() {
          var type = $('#span_form input:radio:checked').val();
          
          showAllAttributes = false;
          
          var entityAttrCount = showAttributesFor(entityAttributeTypes, 'entity', type);
          var eventAttrCount = showAttributesFor(eventAttributeTypes, 'event', type);
          
          // show attribute frames only if at least one attribute is
          // shown, and set size classes appropriately
          if (eventAttrCount > 0) {
            $('#event_attributes').show();
            $('#event_attribute_label').show();
            $('#event_types').
              removeClass('scroll_wrapper_full').
              addClass('scroll_wrapper_upper');
          } else {
            $('#event_attributes').hide();
            $('#event_attribute_label').hide();
            $('#event_types').
              removeClass('scroll_wrapper_upper').
              addClass('scroll_wrapper_full');
          }
          if (entityAttrCount > 0) {
            $('#entity_attributes').show();
            $('#entity_attribute_label').show();
            $('#entity_types').
              removeClass('scroll_wrapper_full').
              addClass('scroll_wrapper_upper');
          } else {
            $('#entity_attributes').hide();
            $('#entity_attribute_label').hide();
            $('#entity_types').
              removeClass('scroll_wrapper_upper').
              addClass('scroll_wrapper_full');
          }
        }
        showValidAttributes();

        // TODO XXX: if seemed quite unexpected/unintuitive that the
        // form was re-displayed while the document still shows the
        // annotation in its old location in the background (check it).
        // The fix of skipping confirm is not really good either, though.
        if (reselectedSpan) { // && !Configuration.confirmModeOn) {
          submitReselect();
        } else {
          dispatcher.post('showForm', [spanForm, true]);
          $('#span_form-ok').focus();
          adjustToCursor(evt, spanForm.parent());
        }
      };

      var submitReselect = function() {
        $(reselectedSpan.rect).removeClass('reselect');
        reselectedSpan = null;
        spanForm.submit();
      };

      var rapidFillSpanTypesAndDisplayForm = function(start, end, text, types) {
        // variant of fillSpanTypesAndDisplayForm for rapid annotation mode
        keymap = spanKeymap;
        $('#rapid_span_selected').text(text);

        // fill types
        var $spanTypeDiv = $('#rapid_span_types_div');
        // remove previously filled, if any
        $spanTypeDiv.empty();
        $.each(types, function(typeNo, typeAndProb) {
          // TODO: this duplicates a part of addSpanTypesToDivInner, unify
          var type = typeAndProb[0];
          var prob = typeAndProb[1];
          var $numlabel = $('<span class="accesskey">'+(typeNo+1)+'</span><span>:</span>');
          var $input = $('<input type="radio" name="rapid_span_type"/>').
              attr('id', 'rapid_span_' + (typeNo+1)).
              attr('value', type);
          var spanBgColor = spanTypes[type] && spanTypes[type].bgColor || '#ffffff';
          spanBgColor = Util.adjustColorLightness(spanBgColor, spanBoxTextBgColorLighten);
          // use preferred label instead of type name if available
          var name = spanTypes[type] && spanTypes[type].name || type;
          var $label = $('<label class="span_type_label"/>').
            attr('for', 'rapid_span_' + (typeNo+1)).
            text(name+' (' + (100.0 * prob).toFixed(1) + '%)');
          $label.css('background-color', spanBgColor);          
          // TODO: check for unnecessary extra wrapping here
          var $content = $('<div class="item_content"/>').
            append($numlabel).
            append($input).
            append($label);
          $spanTypeDiv.append($content);
          // highlight configured hotkey (if any) in text.
          // NOTE: this bit doesn't actually set up the hotkey.
          var hotkeyType = 'span_' + type;
          // TODO: this is clumsy; there should be a better way
          var typeHotkey = null;
          $.each(keymap, function(key, keyType) {
            if (keyType == hotkeyType) {
              typeHotkey = key;
              return false;
            }
          });
          if (typeHotkey) {
            var name = $label.html();
            var replace = true;
            name = name.replace(new RegExp("(&[^;]*?)?(" + typeHotkey + ")", 'gi'),
              function(all, entity, letter) {
                if (replace && !entity) {
                  replace = false;
                  var hotkey = typeHotkey.toLowerCase() == letter
                      ? typeHotkey.toLowerCase()
                      : typeHotkey.toUpperCase();
                  return '<span class="accesskey">' + Util.escapeHTML(hotkey) + '</span>';
                }
                return all;
              });
            $label.html(name);
          }
          // Limit the number of suggestions to the number of numeric keys
          if (typeNo >= 8) {
            return false;
          }
        });
        // fill in some space and the special "Other" option, with key "0" (zero)
        $spanTypeDiv.append($('<div class="item_content">&#160;</div>')); // non-breaking space
        var $numlabel = $('<span class="accesskey">0</span><span>:</span>');        
        var $input = $('<input type="radio" name="rapid_span_type" id="rapid_span_0" value=""/>');
        var $label = $('<label class="span_type_label" for="rapid_span_0" style="background-color:lightgray">Other...</label>');
        var $content = $('<div class="item_content"/>').
          append($numlabel).
          append($input).
          append($label);
        $spanTypeDiv.append($content);

        // set up click event handlers
        rapidSpanForm.find('#rapid_span_types input:radio').click(rapidSpanFormSubmitRadio);

        var firstRadio = $('#rapid_span_form input:radio:first')[0];
        if (firstRadio) {
          firstRadio.checked = true;
        } else {
          dispatcher.post('hideForm');
          dispatcher.post('messages', [[['No valid span types defined', 'error']]]);
          return;
        }
        dispatcher.post('showForm', [rapidSpanForm]);
        rapidAnnotationDialogVisible = true;
        $('#rapid_span_form-ok').focus();
        // TODO: avoid using global for stored click event
//         adjustToCursor(lastRapidAnnotationEvent, rapidSpanForm.parent(),
//                        true, true);
        // TODO: avoid coordinate hack to position roughly at first
        // available selection
        lastRapidAnnotationEvent.clientX -= 55;
        lastRapidAnnotationEvent.clientY -= 115;
        adjustToCursor(lastRapidAnnotationEvent, rapidSpanForm.parent(),
                       false, false);
      };

      var clearArcNotes = function(evt) {
        $('#arc_notes').val('');
      }
      $('#clear_arc_notes_button').button();
      $('#clear_arc_notes_button').click(clearArcNotes);

      var clearSpanNotes = function(evt) {
        $('#span_notes').val('');
      }
      $('#clear_span_notes_button').button();
      $('#clear_span_notes_button').click(clearSpanNotes);

      var clearSpanNorm = function(evt) {
        clearNormalizationUI();
      }
      $('#clear_norm_button').button();
      $('#clear_norm_button').click(clearSpanNorm);

      // invoked on response to ajax request for id lookup
      var setSpanNormText = function(response) {
        if (response.exception) {
          // TODO: better response to failure
          dispatcher.post('messages', [[['Lookup error', 'warning', -1]]]);
          return false;
        }        
        // set input style according to whether we have a valid value
        var $normId = $('#span_norm_id');
        // TODO: make sure the key echo in the response matches the
        // current value of the $idinput
        $normId.attr('data-value', null);
        if (response.value === null) {
          $normId.addClass('invalid_value');
          hideNormalizationRefLink();
        } else {
          $normId.attr('data-value', 'valid');
          updateNormalizationRefLink();
        }
        $('#span_norm_txt').val(response.value);
      }

      // on any change to the normalization DB, clear everything and
      // update link
      var spanNormDbUpdate = function(evt) {
        var normDb = $('span_norm_db').val();
        if (normalizations[normDb]) {
          var norm = normalizations[normDb][0];
          $('#span_norm_id').val(norm[0]).
              attr('data-value', normalizations[normFilled].length == 1 ? 'valid' : 'multi')
          $('#span_norm_txt').val(norm[1]);
        } else {
          clearNormalizationUI();
        }
        updateNormalizationDbLink();
      }
      $('#span_norm_db').change(spanNormDbUpdate);

      // if there's multiple normalisations for the type, allow selection
      var spanNormSelect = function(evt) {
        var normDb = $('#span_norm_db').val();
        if (normalizations[normDb].length > 1) {
          showNormSearchDialog();
          setSpanNormSearchResults({
            header: ['ID', 'Text'],
            items: normalizations[normDb],
          });
        }
      }

      // on any change to the normalization ID, update the text of the
      // reference
      var spanNormIdUpdate = function(evt) {
        var key = $(this).val();
        var db = $('#span_norm_db').val();
        if (key != oldSpanNormIdValue) {
          if (key.match(/^\s*$/)) {
            // don't query empties, just clear instead
            clearNormalizationUI();
          } else {
            dispatcher.post('ajax', [ {
                            action: 'normGetName',
                            database: db,
                            key: key,
                            collection: coll}, 'normGetNameResult']);
          }
          oldSpanNormIdValue = key;
        }
        // TODO make it possible for multiple types of normalisations
        // to survive to save
      }
      // see http://stackoverflow.com/questions/1948332/detect-all-changes-to-a-input-type-text-immediately-using-jquery
      $('#span_norm_id').bind('propertychange keyup input paste', spanNormIdUpdate).
          bind('click', spanNormSelect);
      // nice-looking select for normalization
      $('#span_norm_db').addClass('ui-widget ui-state-default ui-button-text');

      var normSearchDialog = $('#norm_search_dialog');
      initForm(normSearchDialog, {
          width: 800,
          width: 600,
          resizable: true,
          alsoResize: '#norm_search_result_select',
          open: function(evt) {
            keymap = {};
          },
          close: function(evt) {
            // assume that we always want to return to the span dialog
            // on normalization dialog close
            dispatcher.post('showForm', [spanForm, true]);
          },
      });
      $('#norm_search_query').autocomplete({
        source: function(request, callback) {
          var query = $.ui.autocomplete.escapeRegex(request.term);
          var pattern = new RegExp('\\b' + query, 'i');
          callback($.grep(lastNormSearches, function(search) {
            return pattern.test(search.value) || pattern.test(search.id);
          }));
        },
        minLength: 0,
        select: function(evt, ui) {
          evt.stopPropagation();
          normSubmit(ui.item.id, ui.item.value);
        },
        focus: function(evt, ui) {
          // do nothing
        },
      }).autocomplete('instance')._renderItem = function($ul, item) {
        // XXX TODO TEST
        return $('<li></li>').
          data('item.autocomplete', item).
          append('<a>' + Util.escapeHTML(item.value) + '<div class="autocomplete-id">' + Util.escapeHTML(item.id) + "</div></a>").
          appendTo($ul);
      };
      var normSubmit = function(selectedId, selectedTxt) {
        // we got a value; act if it was a submit
        $('#span_norm_id').val(selectedId);
        // don't forget to update this reference value
        oldSpanNormIdValue = selectedId;
        $('#span_norm_txt').val(selectedTxt);
        updateNormalizationRefLink();
        // update history
        var nextLastNormSearches = [
          {
            value: selectedTxt,
            id: selectedId,
          },
        ];
        $.each(lastNormSearches, function(searchNo, search) {
          if (search.id != selectedId || search.value != selectedTxt) {
            nextLastNormSearches.push(search);
          }
        });
        lastNormSearches = nextLastNormSearches;
        lastNormSearches.slice(0, maxNormSearchHistory);
        // Switch dialogs. NOTE: assuming we closed the spanForm when
        // bringing up the normSearchDialog.
        normSearchDialog.dialog('close');
      };
      var normSearchSubmit = function(evt) {
        if (normSearchSubmittable) {
          var selectedId = $('#norm_search_id').val(); 
          var selectedTxt = $('#norm_search_query').val();

          normSubmit(selectedId, selectedTxt);
        } else {
          performNormSearch();
        }
        return false;
      }
      var normSearchSubmittable = false;
      var setNormSearchSubmit = function(enable) {
        $('#norm_search_dialog-ok').button(enable ? 'enable' : 'disable');
        normSearchSubmittable = enable;
      };
      normSearchDialog.submit(normSearchSubmit);
      var chooseNormId = function(evt) {
        var $element = $(evt.target).closest('tr');
        $('#norm_search_result_select tr').removeClass('selected');
        $element.addClass('selected');
        $('#norm_search_query').val($element.attr('data-txt'));
        $('#norm_search_id').val($element.attr('data-id'));
        setNormSearchSubmit(true);
      }
      var chooseNormIdAndSubmit = function(evt) {
        chooseNormId(evt);
        normSearchSubmit(evt);
      }
      var setSpanNormSearchResults = function(response) {
        if (response.exception) {
          // TODO: better response to failure
          dispatcher.post('messages', [[['Lookup error', 'warning', -1]]]);
          return false;
        }

        if (response.items.length == 0) {
          // no results
          $('#norm_search_result_select thead').empty();
          $('#norm_search_result_select tbody').empty();
          dispatcher.post('messages', [[['No matches to search.', 'comment']]]);
          return false;
        }

        // TODO: avoid code duplication with showFileBrowser()

        var html = ['<tr>'];
        $.each(response.header, function(headNo, head) {
          html.push('<th>' + Util.escapeHTML(head[0]) + '</th>');
        });
        html.push('</tr>');
        $('#norm_search_result_select thead').html(html.join(''));

        html = [];
        var len = response.header.length;
        $.each(response.items, function(itemNo, item) {
          // NOTE: assuming ID is always the first datum in the item
          // and that the preferred text is always the second
          // TODO: Util.escapeQuotes would be expected to be
          // sufficient here, but that appears to give "DOM Exception
          // 11" in cases (try e.g. $x.html('<p a="A&B"/>'). Why? Is
          // this workaround OK?
          html.push('<tr'+
                    ' data-id="'+Util.escapeHTMLandQuotes(item[0])+'"'+
                    ' data-txt="'+Util.escapeHTMLandQuotes(item[1])+'"'+
                    '>');
          for (var i=0; i<len; i++) {
            html.push('<td>' + Util.escapeHTML(item[i]) + '</td>');
          }
          html.push('</tr>');
        });
        $('#norm_search_result_select tbody').html(html.join(''));

        $('#norm_search_result_select tbody').find('tr').
            click(chooseNormId).
            dblclick(chooseNormIdAndSubmit);

        // TODO: sorting on click on header (see showFileBrowser())
      }
      var performNormSearch = function() {
        var val = $('#norm_search_query').val();
        var db = $('#span_norm_db').val();
        dispatcher.post('ajax', [ {
                        action: 'normSearch',
                        database: db,
                        name: val,
                        collection: coll}, 'normSearchResult']);
      }
      $('#norm_search_button').click(performNormSearch);
      $('#norm_search_query').focus(function() {
        setNormSearchSubmit(false);
      });
      var showNormSearchDialog = function() {
        // take default search string from annotated span and clear ID entry
        // (if the selected string was correct, search wouldn't be necessary)
        $('#norm_search_id').val('');
        $('#norm_search_query').val($('#span_selected').text());
        // blank the table
        $('#norm_search_result_select thead').empty();
        $('#norm_search_result_select tbody').empty();        
        // TODO: support for two (or more) dialogs open at the same time
        // so we don't need to hide this before showing normSearchDialog
        dispatcher.post('hideForm');
        $('#norm_search_button').val('Search ' + $('#span_norm_db').val());
        setNormSearchSubmit(false);
        dispatcher.post('showForm', [normSearchDialog]);
        $('#norm_search_query').focus().select();
      }
      $('#span_norm_txt').click(showNormSearchDialog);
      $('#norm_search_button').button();

      var arcFormSubmitRadio = function(evt) {
        // TODO: check for confirm_mode?
        arcFormSubmit(evt, $(evt.target));
      }

      var arcFormSubmit = function(evt, typeRadio) {
        typeRadio = typeRadio || $('#arc_form input:radio:checked');
        var type = typeRadio.val();
        dispatcher.post('hideForm', [arcForm]);

        arcOptions.type = type;
        arcOptions.comment = $('#arc_notes').val();
        dispatcher.post('ajax', [arcOptions, 'edited']);
        return false;
      };

      var fillArcTypesAndDisplayForm = function(evt, originType, targetType, arcType, arcId) {
        var noArcs = true;
        keymap = {};

        // separate out possible numeric suffix from type
        var noNumArcType;
        if (arcType) {
            var splitType = arcType.match(/^(.*?)(\d*)$/);
            noNumArcType = splitType[1];
        }

        var isEquiv =
          relationTypesHash &&
          relationTypesHash[noNumArcType] &&
          relationTypesHash[noNumArcType].properties &&
          relationTypesHash[noNumArcType].properties.symmetric &&
          relationTypesHash[noNumArcType].properties.transitive;

        var $scroller = $();
        var mapOf$containers = {};
        var mapOf$items = {};
        var mapOfParents = {};
        if (spanTypes[originType]) {
          var arcTypes = spanTypes[originType].arcs;
          $scroller = $('#arc_roles .scroller').empty();

          // lay them out into the form
          $.each(arcTypes || [], function(arcTypeNo, arcDesc) {
            if (arcDesc.targets && arcDesc.targets.indexOf(targetType) != -1) {
              var arcTypeName = arcDesc.type;
              var relType = relationTypesHash && relationTypesHash[arcTypeName];

              var isThisEquiv = relType &&
                relType.properties &&
                relType.properties.symmetric &&
                relType.properties.transitive;

              // do not allow equiv<->non-equiv change options
              if (arcType && isEquiv != isThisEquiv) return;

              var displayName = ((arcDesc.labels && arcDesc.labels[0]) || 
                                 arcTypeName);
              var $input = $('<input id="arc_' + arcTypeName + '" type="radio" name="arc_type" value="' + arcTypeName + '"/>');
              var $label = $('<label class="arc_type_label" for="arc_' + arcTypeName + '"/>').text(displayName);
              var $collapsible = $('<div class="collapsible"/>');
              var $content = $('<div class="item_content"/>').
                append($input).
                append($label).
                append($collapsible);
              var $div = $('<div class="item"/>');
              if (relType && relType.children && relType.children.length) {
                var $collapser = $('<div class="collapser"/>').data('rel-name', arcTypeName);
                $div.append($collapser);
                $.each(relType.children, function(childRelNo, childRel) {
                  mapOfParents[childRel.type] = arcTypeName;
                });
                if (!collapsed[arcTypeName]) {
                  $collapser.addClass('open');
                  $collapsible.addClass('open');
                }
              }
              $div.append($content);
              mapOf$containers[arcTypeName] = $collapsible;
              mapOf$items[arcTypeName] = $div
              if (arcDesc.hotkey) {
                keymap[arcDesc.hotkey] = '#arc_' + arcTypeName;
                var name = $label.html();
                var replace = true;
                name = name.replace(new RegExp("(&[^;]*?)?(" + arcDesc.hotkey + ")", 'gi'),
                  function(all, entity, letter) {
                    if (replace && !entity) {
                      replace = false;
                      var hotkey = arcDesc.hotkey.toLowerCase() == letter
                          ? arcDesc.hotkey.toLowerCase()
                          : arcDesc.hotkey.toUpperCase();
                      return '<span class="accesskey">' + Util.escapeHTML(hotkey) + '</span>';
                    }
                    return all;
                  });
                $label.html(name);
              }

              noArcs = false;
            }
          });

          $.each(mapOf$items, function(name, $div) {
            var parent = mapOfParents[name];
            $div.appendTo(parent ? mapOf$containers[parent] : $scroller);
          });
        }

        if (noArcs) {
          if (arcId) {
            // let the user delete or whatever, even on bad config
            // (note that what's shown to the user is w/o possible num suffix)
            var $checkbox = $('<input id="arc_' + arcType + '" type="hidden" name="arc_type" value="' + noNumArcType + '"/>');
            $scroller.append($checkbox);
          } else {
            // can't make a new arc
            dispatcher.post('messages',
              [[["No choices for " +
                 Util.spanDisplayForm(spanTypes, originType) +
                 " -> " +
                 Util.spanDisplayForm(spanTypes, targetType),
                 'warning']]]);
            return;
          }
        }

        var reversalPossible = false;
        if (arcId) {
          // something was selected
          var focus = arcId instanceof Array ? arcId : [arcId];
          var hash = new URLHash(coll, doc, { focus: [focus] }).getHash();
          $('#arc_highlight_link').attr('href', hash).show(); // TODO incorrect
          var el = $('#arc_' + arcType)[0];
          if (el) {
            el.checked = true;
          } else {
              // try w/o numeric suffix
              el = $('#arc_' + noNumArcType)[0];
              if (el) {
                  el.checked = true;
              }
          }

          $('#arc_form_reselect, #arc_form_delete').show();
          keymap[$.ui.keyCode.DELETE] = 'arc_form_delete';
          keymap[$.ui.keyCode.INSERT] = 'arc_form_reselect';

          var backTargetType = spanTypes[targetType];
          if (backTargetType) {
            $.each(backTargetType.arcs || [], function(backArcTypeNo, backArcDesc) {
              if ($.inArray(originType, backArcDesc.targets || []) != -1) {
                var relType = relationTypesHash[backArcDesc.type];
                reversalPossible = relType && relType.properties && (!relType.properties.symmetric);
                return false; // terminate the loop
              }
            });
          }

          arcForm.dialog('option', { title: 'Edit Annotation' });
        } else {
          // new arc
          $('#arc_highlight_link').hide();
          el = $('#arc_form input:radio:first')[0];
          if (el) {
            el.checked = true;
          }

          $('#arc_form_reselect, #arc_form_delete, #arc_form_reverse').hide();

          arcForm.dialog('option', { title: 'New Annotation' });
        }
        if (reversalPossible) {
          $('#arc_form_reverse').show();
          keymap['S-' + $.ui.keyCode.INSERT] = 'arc_form_reverse';
        } else {
          $('#arc_form_reverse').hide();
        }

        if (!Configuration.confirmModeOn) {
          arcForm.find('#arc_roles input:radio').click(arcFormSubmitRadio);
        }

        var arcAnnotatorNotes;
        var isMultiRelation = arcId && arcId instanceof Array
        var isBinaryRelation = arcId && !(arcId instanceof Array);
        if (isBinaryRelation) {
          // only for relation arcs
          var ed = data.eventDescs[arcId];
          arcAnnotatorNotes = ed && ed.annotatorNotes;
        }
        if (arcAnnotatorNotes) {
          $('#arc_notes').val(arcAnnotatorNotes);
        } else {
          $('#arc_notes').val('');
        }

        // disable notes for arc types that don't support storage (#945)
        if(isMultiRelation || isEquiv) {
          // disable the actual input
          $('#arc_notes').attr('disabled', 'disabled');
          // add to fieldset for style
          $('#arc_notes_fieldset').attr('disabled', 'disabled');
        } else {
          $('#arc_notes').removeAttr('disabled')
          $('#arc_notes_fieldset').removeAttr('disabled')
        }

        dispatcher.post('showForm', [arcForm]);
        $('#arc_form-ok').focus();
        adjustToCursor(evt, arcForm.parent());
      };
      

      var reverseArc = function(evt) {
        var eventDataId = $(evt.target).attr('data-arc-ed');
        dispatcher.post('hideForm');
        arcOptions.action = 'reverseArc';
        delete arcOptions.old_target;
        delete arcOptions.old_type;
        dispatcher.post('ajax', [arcOptions, 'edited']);
      };

      var deleteArc = function(evt) {
        if (Configuration.confirmModeOn && !confirm("Are you sure you want to delete this annotation?")) {
          return;
        }
        var eventDataId = $(evt.target).attr('data-arc-ed');
        dispatcher.post('hideForm');
        arcOptions.action = 'deleteArc';
        dispatcher.post('ajax', [arcOptions, 'edited']);
      };

      var reselectArc = function(evt) {
        dispatcher.post('hideForm');
        svgElement.addClass('reselect');
        $('g[data-from="' + arcOptions.origin + '"][data-to="' + arcOptions.target + '"]').addClass('reselect');
        startArcDrag(arcOptions.origin);
      };

      var arcForm = $('#arc_form');
      dispatcher.post('initForm', [arcForm, {
          width: 500,
          buttons: [{
              id: 'arc_form_reverse',
              text: "Reverse",
              click: reverseArc
            }, {
              id: 'arc_form_delete',
              text: "Delete",
              click: deleteArc
            }, {
              id: 'arc_form_reselect',
              text: 'Reselect',
              click: reselectArc
            }],
          alsoResize: '#arc_roles',
          close: function(evt) {
            keymap = null;
          }
        }]);
      arcForm.submit(arcFormSubmit);
      // set button tooltips (@amadanmath: can this be done in init?)
      $('#arc_form_reselect').attr('title', 'Re-select the annotation this connects into.');
      $('#arc_form_delete').attr('title', 'Delete this annotation.');

      var stopArcDrag = function(target) {
        if (arcDragOrigin) {
          if (!target) {
            target = $('.badTarget');
          }
          target.removeClass('badTarget');
          arcDragOriginGroup.removeClass('highlight');
          if (target) {
            target.parent().removeClass('highlight');
          }
          arcDragArc.setAttribute('visibility', 'hidden');
          arcDragOrigin = null;
          if (arcOptions) {
              $('g[data-from="' + arcOptions.origin + '"][data-to="' + arcOptions.target + '"]').removeClass('reselect');
          }
          svgElement.removeClass('reselect');
          $(arcTargetRects).removeClass('reselectTarget');
          arcTargets = [];
          arcTargetRects = [];
        }
        svgElement.removeClass('unselectable');
      };

      var tryToAnnotate = function(evt) {
        var sel = window.getSelection();
        var theFocusNode = sel.focusNode;
        if (!theFocusNode) return;

        var chunkIndexFrom = sel.anchorNode && $(sel.anchorNode.parentNode).attr('data-chunk-id');
        var chunkIndexTo;
        chunkIndexTo = $(theFocusNode.parentNode).attr('data-chunk-id');
        if (!chunkIndexTo) {
          theFocusNode = $(theFocusNode).children()[0].firstChild;
          chunkIndexTo = $(theFocusNode.parentNode).attr('data-chunk-id');
        }
        // var chunkIndexTo = sel.focusNode && ($(sel.focusNode.parentNode).attr('data-chunk-id') || $(sel.focusNode).children().first().attr('data-chunk-id'));

        // fallback for firefox (at least):
        // it's unclear why, but for firefox the anchor and focus
        // node parents are always undefined, the the anchor and
        // focus nodes themselves do (often) have the necessary
        // chunk ID. However, anchor offsets are almost always
        // wrong, so we'll just make a guess at what the user might
        // be interested in tagging instead of using what's given.
        var anchorOffset = null;
        var focusOffset = null;
        if (chunkIndexFrom === undefined && chunkIndexTo === undefined &&
            $(sel.anchorNode).attr('data-chunk-id') &&
            $(theFocusNode).attr('data-chunk-id')) {
          // A. Scerri FireFox chunk

          var range = sel.getRangeAt(0);
          var svgOffset = $(svg._svg).offset();
          var flip = false;
          var tries = 0;
          while (tries < 2) {
            var sp = svg._svg.createSVGPoint();
            sp.x = (flip ? evt.pageX : dragStartedAt.pageX) - svgOffset.left;
            sp.y = (flip ? evt.pageY : dragStartedAt.pageY) - (svgOffset.top + 8);
            var startsAt = range.startContainer;
            anchorOffset = startsAt.getCharNumAtPosition(sp);
            chunkIndexFrom = startsAt && $(startsAt).attr('data-chunk-id');
            if (anchorOffset != -1) {
              break;
            }
            flip = true;
            tries++;
          }
          sp.x = (flip ? dragStartedAt.pageX : evt.pageX) - svgOffset.left;
          sp.y = (flip ? dragStartedAt.pageY : evt.pageY) - (svgOffset.top + 8);
          var endsAt = range.endContainer;
          focusOffset = endsAt.getCharNumAtPosition(sp);

          if (range.startContainer == range.endContainer && anchorOffset > focusOffset) {
            var t = anchorOffset;
            anchorOffset = focusOffset;
            focusOffset = t;
            flip = false;
          }
          if (focusOffset != -1) {
            focusOffset++;
          }
          chunkIndexTo = endsAt && $(endsAt).attr('data-chunk-id');

          //console.log('fallback from', data.chunks[chunkIndexFrom], anchorOffset);
          //console.log('fallback to', data.chunks[chunkIndexTo], focusOffset);
        } else {
          // normal case, assume the exact offsets are usable
          anchorOffset = sel.anchorOffset;
          focusOffset = sel.focusOffset;
        }

        if (evt.type == 'keydown') {
          var offset = sel.focusOffset;
          if (offset >= theFocusNode.length) {
            offset = theFocusNode.length - 1;
          }
          var endpos = theFocusNode.parentNode.getEndPositionOfChar(offset);
          var svgpos = $(svg._svg).offset();
          evt.clientX = endpos.x + svgpos.left - window.scrollX;
          evt.clientY = endpos.y + svgpos.top - window.scrollY;
        }

        if (chunkIndexFrom !== undefined && chunkIndexTo !== undefined) {
          var chunkFrom = data.chunks[chunkIndexFrom];
          var chunkTo = data.chunks[chunkIndexTo];
          var selectedFrom = chunkFrom.from + anchorOffset;
          var selectedTo = chunkTo.from + focusOffset;
          sel.removeAllRanges();

          if (selectedFrom > selectedTo) {
            var tmp = selectedFrom; selectedFrom = selectedTo; selectedTo = tmp;
          }
          // trim
          while (selectedFrom < selectedTo && " \n\t".indexOf(data.text.substr(selectedFrom, 1)) !== -1) selectedFrom++;
          while (selectedFrom < selectedTo && " \n\t".indexOf(data.text.substr(selectedTo - 1, 1)) !== -1) selectedTo--;

          // shift+click allows zero-width spans
          if (selectedFrom === selectedTo && !evt.shiftKey) {
            // simple click (zero-width span)
            return;
          }

          var newOffset = [selectedFrom, selectedTo];
          if (reselectedSpan) {
            var newOffsets = reselectedSpan.offsets.slice(0); // clone
            spanOptions.old_offsets = JSON.stringify(reselectedSpan.offsets);
            if (selectedFragment !== null) {
              if (selectedFragment !== false) {
                newOffsets.splice(selectedFragment, 1);
              }
              newOffsets.push(newOffset);
              newOffsets.sort(Util.cmpArrayOnFirstElement);
              spanOptions.offsets = newOffsets;
            } else {
              spanOptions.offsets = [newOffset];
            }
          } else {
            spanOptions = {
              action: 'createSpan',
              offsets: [newOffset]
            }
          }


/* In relation to #786, removed the cross-sentence checking code
          var crossSentence = true;
          $.each(sourceData.sentence_offsets, function(sentNo, startEnd) {
            if (selectedTo <= startEnd[1]) {
              // this is the sentence

              if (selectedFrom >= startEnd[0]) {
                crossSentence = false;
              }
              return false;
            }
          });

          if (crossSentence) {
            // attempt to annotate across sentence boundaries; not supported
            dispatcher.post('messages', [[['Error: cannot annotate across a sentence break', 'error']]]);
            if (reselectedSpan) {
              $(reselectedSpan.rect).removeClass('reselect');
            }
            reselectedSpan = null;
            svgElement.removeClass('reselect');
          } else
*/
          if (lockOptions) {
            spanFormSubmit();
            dispatcher.post('logAction', ['spanLockNewSubmitted']);
          } else if (!Configuration.rapidModeOn || reselectedSpan != null) {
            // normal span select in standard annotation mode
            // or reselect: show selector
            var spanText = data.text.substring(selectedFrom, selectedTo);
            fillSpanTypesAndDisplayForm(evt, spanText, reselectedSpan);
            // for precise timing, log annotation display to user.
            dispatcher.post('logAction', ['spanSelected']);
          } else {
            // normal span select in rapid annotation mode: call
            // server for span type candidates
            var spanText = data.text.substring(selectedFrom, selectedTo);
            // TODO: we're currently storing the event to position the
            // span form using adjustToCursor() (which takes an event),
            // but this is clumsy and suboptimal (user may have scrolled
            // during the ajax invocation); think of a better way.
            lastRapidAnnotationEvent = evt;
            dispatcher.post('ajax', [ { 
                            action: 'suggestSpanTypes',
                            collection: coll,
                            'document': doc,
                            start: selectedFrom,
                            end: selectedTo,
                            text: spanText,
                            model: $('#rapid_model').val(),
                            }, 'suggestedSpanTypes']);
          }
        }
      };

      var onMouseUp = function(evt) {
        if (that.user === null) return;

        var target = $(evt.target);

        // three things that are clickable in SVG
        var targetSpanId = target.data('span-id');
        var targetChunkId = target.data('chunk-id');
        var targetArcRole = target.data('arc-role');
        if (!(targetSpanId !== undefined || targetChunkId !== undefined || targetArcRole !== undefined)) {
          // misclick
          clearSelection();
          stopArcDrag(target);
          return;
        }

        if (arcDragJustStarted && (Util.isMac ? evt.metaKey : evt.ctrlKey)) {
          // is it arc drag start (with ctrl or alt)? do nothing special

        } else if (arcDragOrigin) {
          // is it arc drag end?
          var origin = arcDragOrigin;
          var id = target.attr('data-span-id');
          var targetValid = arcTargets.indexOf(id) != -1;
          stopArcDrag(target);
          if (id && origin != id && targetValid) {
            var originSpan = data.spans[origin];
            var targetSpan = data.spans[id];
            if (arcOptions && arcOptions.old_target) {
              arcOptions.target = targetSpan.id;
              dispatcher.post('ajax', [arcOptions, 'edited']);
            } else {
              arcOptions = {
                action: 'createArc',
                origin: originSpan.id,
                target: targetSpan.id,
                collection: coll,
                'document': doc
              };
              $('#arc_origin').text(Util.spanDisplayForm(spanTypes, originSpan.type)+' ("'+originSpan.text+'")');
              $('#arc_target').text(Util.spanDisplayForm(spanTypes, targetSpan.type)+' ("'+targetSpan.text+'")');
              fillArcTypesAndDisplayForm(evt, originSpan.type, targetSpan.type);
              // for precise timing, log dialog display to user.
              dispatcher.post('logAction', ['arcSelected']);
            }
          }
        } else if (!(Util.isMac ? evt.metaKey : evt.ctrlKey)) {
          // if not, then is it span selection? (ctrl key cancels)
          tryToAnnotate(evt);
        }
      };

      var receivedSuggestedSpanTypes = function(sugg) {
        if (sugg.exception) {
          // failed in one way or another; assume rapid mode cannot be
          // used.
          dispatcher.post('messages', [[['Rapid annotation mode error; returning to normal mode.', 'warning', -1]]]);
          setAnnotationSpeed(2);
          dispatcher.post('configurationUpdated');
          return false;
        }

        // make sure the suggestions are for the current collection and document
        if (sugg.collection != coll || sugg.document != doc) {
          dispatcher.post('messages', [[['Error: collection/document mismatch for span suggestions', 'error']]]);
          return false;
        }
        // initialize for submission
        // TODO: is this a reasonable place to do this?
        rapidSpanOptions = {
          offsets: [[sugg.start, sugg.end]],
        };
        rapidFillSpanTypesAndDisplayForm(sugg.start, sugg.end, sugg.text, sugg.types);
      };

      var collapsed = {}
      var toggleCollapsible = function($el, state) {
        var opening = state !== undefined ? state : !$el.hasClass('open');
        var $collapsible = $el.parent().find('.collapsible:first');
        var relName = $el.data('rel-name');
        if (relName) {
          collapsed[relName] = !collapsed[relName];
        }
        if (opening) {
          $collapsible.addClass('open');
          $el.addClass('open');
        } else {
          $collapsible.removeClass('open');
          $el.removeClass('open');
        }
      };

      var collapseHandler = function(evt) {
        toggleCollapsible($(evt.target));
      }
      $('#arc_roles, #entity_types').on('click', '.collapser', collapseHandler);

      var spanFormSubmitRadio = function(evt) {
        if (Configuration.confirmModeOn) {
          showValidAttributes();
          showValidNormalizations();
          $('#span_form-ok').focus();
        } else {
          spanFormSubmit(evt, $(evt.target));
        }
      }

      var rapidSpanFormSubmitRadio = function(evt) {
        rapidSpanFormSubmit(evt, $(evt.target));
      }

      var rememberData = function(_data) {
        if (_data && !_data.exception) {
          data = _data;
        }
      };

      var addSpanTypesToDivInner = function($parent, types, category) {
        if (!types) return;

        $.each(types, function(typeNo, type) {
          if (type === null) {
            $parent.append('<hr/>');
          } else {
            var name = type.name;
            var $input = $('<input type="radio" name="span_type"/>').
              attr('id', 'span_' + type.type).
              attr('value', type.type);
            if (category) {
              $input.attr('category', category);
            }
            // use a light version of the span color as BG
            var spanBgColor = spanTypes[type.type] && spanTypes[type.type].bgColor || '#ffffff';
            spanBgColor = Util.adjustColorLightness(spanBgColor, spanBoxTextBgColorLighten);
            var $label = $('<label class="span_type_label"/>').
              attr('for', 'span_' + type.type).
              text(name);
            if (type.unused) {
              $input.attr({
                disabled: 'disabled',
                unused: 'unused'
              });
              $label.css('font-weight', 'bold');
            } else {
              $label.css('background-color', spanBgColor);
            }
            var $collapsible = $('<div class="collapsible open"/>');
            var $content = $('<div class="item_content"/>').
              append($input).
              append($label).
              append($collapsible);
            var $div = $('<div class="item"/>');
            if (type.children.length) {
              var $collapser = $('<div class="collapser open"/>');
              $div.append($collapser)
            }
            $div.append($content);
            addSpanTypesToDivInner($collapsible, type.children, category);
            $parent.append($div);
            if (type.hotkey) {
              spanKeymap[type.hotkey] = 'span_' + type.type;
              var name = $label.html();
              var replace = true;
              name = name.replace(new RegExp("(&[^;]*?)?(" + type.hotkey + ")", 'gi'),
                function(all, entity, letter) {
                  if (replace && !entity) {
                    replace = false;
                    var hotkey = type.hotkey.toLowerCase() == letter
                        ? type.hotkey.toLowerCase()
                        : type.hotkey.toUpperCase();
                    return '<span class="accesskey">' + Util.escapeHTML(hotkey) + '</span>';
                  }
                  return all;
                });
              $label.html(name);
            }
          }
        });
      };
      var addSpanTypesToDiv = function($top, types, heading) {
        $scroller = $('<div class="scroller"/>');
        $legend = $('<legend/>').text(heading);
        $fieldset = $('<fieldset/>').append($legend).append($scroller);
        $top.append($fieldset);
        addSpanTypesToDivInner($scroller, types);
      };
      var addAttributeTypesToDiv = function($top, types, category) {
        $.each(types, function(attrNo, attr) {
          var escapedType = Util.escapeQuotes(attr.type);
          var attrId = category+'_attr_'+escapedType;
          var $span = $('<span class="attribute_type_label"/>').appendTo($top);
          if (attr.unused) {
            $('<input type="hidden" id="'+attrId+'" value=""/>').appendTo($span);
          } else if (attr.bool) {
            var escapedName = Util.escapeQuotes(attr.name);
            var $input = $('<input type="checkbox" id="'+attrId+
                           '" value="' + escapedType + 
                           '" category="' + category + '"/>');
            var $label = $('<label for="'+attrId+
                           '" data-bare="' + escapedName + '">&#x2610; ' + 
                           escapedName + '</label>');
            $span.append($input).append($label);
            $input.button();
            $input.change(onBooleanAttrChange);
          } else {
            // var $div = $('<div class="ui-button ui-button-text-only attribute_type_label"/>');
            $span.text(attr.name);
            $span.append(':&#160;');
            var $select = $('<select id="'+attrId+'" class="ui-widget ui-state-default ui-button-text" category="' + category + '"/>');
            var $option = $('<option class="ui-state-default" value=""/>').text('?');
            $select.append($option);
            $.each(attr.values, function(valueNo, value) {
              $option = $('<option class="ui-state-active" value="' + Util.escapeQuotes(value.name) + '"/>').text(value.name);
              $select.append($option);
            });
            $span.append($select);
            $select.combobox();
            $select.change(onMultiAttrChange);
          }
        });
      }

      var setSpanTypeSelectability = function(category) {
        // TODO: this implementation is incomplete: we should ideally
        // disable not only categories of types (events or entities),
        // but the specific set of types that are incompatible with
        // the current attribute settings.
        
        // just assume all attributes are event attributes
        // TODO: support for entity attributes
        // TODO2: the above comment is almost certainly false, check and remove
        $('#span_form input:not([unused])').removeAttr('disabled');
        var $toDisable;
        if (category == "event") {
          $toDisable = $('#span_form input[category="entity"]');
        } else if (category == "entity") {
          $toDisable = $('#span_form input[category="event"]');
        } else {
          console.error('Unrecognized attribute category:', category);
          $toDisable = $();
        }
        var $checkedToDisable = $toDisable.filter(':checked');
        $toDisable.attr('disabled', true);
        // the disable may leave the dialog in a state where nothing
        // is checked, which would cause error on "OK". In this case,
        // check the first valid choice.
        if ($checkedToDisable.length) {
          var $toCheck = $('#span_form input[category="' + category + '"][disabled!="disabled"]:first');
          // so weird, attr('checked', 'checked') fails sometimes, so
          // replaced with more "metal" version
          $toCheck[0].checked = true;
        }
      }

      var onMultiAttrChange = function(evt) {
        if ($(this).val() == '') {
          $('#span_form input:not([unused])').removeAttr('disabled');
        } else {
          var attrCategory = evt.target.getAttribute('category');
          setSpanTypeSelectability(attrCategory);
          if (evt.target.selectedIndex) {
            $(evt.target).addClass('ui-state-active');
          } else {
            $(evt.target).removeClass('ui-state-active');
          }
        }
      }

      var onBooleanAttrChange = function(evt) {
        if (evt.type == 'change') { // ignore the click event on the UI element
          var attrCategory = evt.target.getAttribute('category');
          setSpanTypeSelectability(attrCategory);
          updateCheckbox($(evt.target));
        }
      };

      var rememberSpanSettings = function(response) {
        spanKeymap = {};

        // TODO: check for exceptions in response

        // fill in entity and event types
        var $entityScroller = $('#entity_types div.scroller').empty();
        addSpanTypesToDivInner($entityScroller, response.entity_types, 'entity');
        var $eventScroller = $('#event_types div.scroller').empty();
        addSpanTypesToDivInner($eventScroller, response.event_types, 'event');

        // fill in attributes
        var $entattrs = $('#entity_attributes div.scroller').empty();
        addAttributeTypesToDiv($entattrs, entityAttributeTypes, 'entity');

        var $eveattrs = $('#event_attributes div.scroller').empty();
        addAttributeTypesToDiv($eveattrs, eventAttributeTypes, 'event');

        // fill search options in span dialog
        searchConfig = response.search_config;
        var $searchlinks  = $('#span_search_links').empty();
        var $searchlinks2 = $('#viewspan_search_links').empty();
        var firstLink=true;
        var linkFilled=false;
        if (searchConfig) {
          $.each(searchConfig, function(searchNo, search) {
            if (!firstLink) {
              $searchlinks.append(',\n')
              $searchlinks2.append(',\n')
            }
            firstLink=false;
            $searchlinks.append('<a target="_blank" id="span_'+search[0]+'" href="#">'+search[0]+'</a>');
            $searchlinks2.append('<a target="_blank" id="viewspan_'+search[0]+'" href="#">'+search[0]+'</a>');
            linkFilled=true;
          });
        }
        if (linkFilled) {
          $('#span_search_fieldset').show();
          $('#viewspan_search_fieldset').show();
        } else {
          $('#span_search_fieldset').hide();
          $('#viewspan_search_fieldset').hide();
        }

        spanForm.find('#entity_types input:radio').click(spanFormSubmitRadio);
        spanForm.find('#event_types input:radio').click(spanFormSubmitRadio);
      };

      var tagCurrentDocument = function(taggerId) {
        var tagOptions = {
          action: 'tag',
          collection: coll,
          'document': doc,
          tagger: taggerId,
        };
        dispatcher.post('ajax', [tagOptions, 'edited']);
      }

      var setupTaggerUI = function(response) {
        var taggers = response.ner_taggers || [];
        $taggerButtons = $('#tagger_buttons').empty();
        $.each(taggers, function(taggerNo, tagger) {
          // expect a tuple with ID, name, model, and URL
          var taggerId = tagger[0];
          var taggerName = tagger[1];
          var taggerModel = tagger[2];
          if (!taggerId || !taggerName || !taggerModel) {
            dispatcher.post('messages', [[['Invalid tagger specification received from server', 'error']]]);
            return true; // continue
          }
          var $row = $('<div class="optionRow"/>');
          var $label = $('<span class="optionLabel">'+Util.escapeHTML(taggerName)+'</span>');
          var $button = $('<input id="tag_'+Util.escapeHTML(taggerId)+'_button" type="button" value="'+Util.escapeHTML(taggerModel)+'" tabindex="-1" title="Automatically tag the current document."/>');
          $row.append($label).append($button);
          $taggerButtons.append($row);
          $button.click(function(evt) {
            tagCurrentDocument(taggerId);
          });
        });
        $taggerButtons.find('input').button();
        // if nothing was set up, hide the whole fieldset and show
        // a message to this effect, else the other way around
        if ($taggerButtons.find('input').length == 0) {
          $('#auto_tagging_fieldset').hide();
          $('#no_tagger_message').show();
        } else {
          $('#auto_tagging_fieldset').show();
          $('#no_tagger_message').hide();
        }
      }

      // recursively traverses type hierarchy (entity_types or
      // event_types) and stores normalizations in normDbsByType.
      var rememberNormDbsForType = function(types) {
        if (!types) return;

        $.each(types, function(typeNo, type) {
          if (type === null) {
            // spacer, no-op
          } else {
            normDbsByType[type.type] = type.normalizations || [];
            if (type.children.length) {
              rememberNormDbsForType(type.children);
            }
          }
        });
      };

      var setupNormalizationUI = function(response) {
        var norm_resources = response.normalization_config || [];
        var $norm_select = $('#span_norm_db');
        // clear possible existing
        $norm_select.empty();
        // fill in new
        html = [];
        $.each(norm_resources, function(normNo, norm) {
          var normName = norm[0], normUrl = norm[1], normUrlBase = norm[2];
          var serverDb = norm[3];
          html.push('<option value="'+Util.escapeHTML(normName)+'">'+
                    Util.escapeHTML(normName)+'</option>');
          // remember the urls for updates
          normDbUrlByDbName[normName] = normUrl;
          normDbUrlBaseByDbName[normName] = normUrlBase;
        });
        // remember per-type appropriate DBs
        normDbsByType = {};
        rememberNormDbsForType(response.entity_types);
        rememberNormDbsForType(response.event_types);
        // set up HTML
        $norm_select.html(html.join(''));
        // if we have nothing, just hide the whole thing
        if (!norm_resources.length) {
          $('#norm_fieldset').hide();
        } else {
          $('#norm_fieldset').show();
        }
      }

      // hides the reference link in the normalization UI
      var hideNormalizationRefLink = function() {
        $('#span_norm_ref_link').hide();
      }

      // updates the reference link in the normalization UI according
      // to the current value of the normalization DB and ID.
      var updateNormalizationRefLink = function() {
        var $normId = $('#span_norm_id');
        var $normLink = $('#span_norm_ref_link');
        var normId = $normId.val();
        var $normDb = $('#span_norm_db');
        var normDb = $normDb.val();
        if (!normId || !normDb || normId.match(/^\s*$/)) {
          $normLink.hide();
        } else {
          var base = normDbUrlBaseByDbName[normDb];
          // assume hidden unless everything goes through
          $normLink.hide();
          if (!base) {
            // base URL is now optional, just skip link generation if not set
            ;
          } else if (base.indexOf('%s') == -1) {
            dispatcher.post('messages', [[['Base URL "'+base+'" for '+normDb+' does not contain "%s"', 'error']]]);
          } else {
            // TODO: protect against strange chars in ID
            link = base.replace('%s', normId);
            $normLink.attr('href', link);
            $normLink.show();
          }
        }
      }

      // updates the DB search link in the normalization UI according
      // to the current value of the normalization DB.
      var updateNormalizationDbLink = function() {
        var $dbLink = $('#span_norm_db_link');
        var $normDb = $('#span_norm_db');
        var normDb = $normDb.val();
        if (!normDb) return; // no normalisation configured
        var link = normDbUrlByDbName[normDb];
        if (!link || link.match(/^\s*$/)) {
          dispatcher.post('messages', [[['No URL for '+normDb, 'error']]]);
          $dbLink.hide();
        } else {
          // TODO: protect against weirdness in DB link
          $dbLink.attr('href', link);
          $dbLink.show();
        }
      }

      // resets user-settable normalization-related UI elements to a
      // blank state (does not blank #span_norm_db <select>).
      var clearNormalizationUI = function() {
        var $normId = $('#span_norm_id');
        var $normText = $('#span_norm_txt');
        $normId.val('');
        oldSpanNormIdValue = '';
        $normId.attr('data-value', null);
        $normText.val('');
        updateNormalizationRefLink();
      }

      // returns the normalizations currently filled in the span
      // dialog, or empty list if there are none
      var spanNormalizations = function() {
        // Note that only no or one normalization is supported in the
        // UI at the moment.
        var normalizations = [];
        var normDb = $('#span_norm_db').val();
        var normId = $('#span_norm_id').val();
        var normText = $('#span_norm_txt').val();
        // empty ID -> no normalization
        if (!normId.match(/^\s*$/)) {
          normalizations.push([normDb, normId, normText]);
        }
        return normalizations;
      }

      // returns attributes that are valid for the selected type in
      // the span dialog
      var spanAttributes = function(typeRadio) {
        typeRadio = typeRadio || $('#span_form input:radio:checked');
        var attributes = {};
        var attributeTypes;
        var category = typeRadio.attr('category');
        if (category == 'entity') {
          attributeTypes = entityAttributeTypes;
        } else if (category == 'event') {
          attributeTypes = eventAttributeTypes;
        } else {
          console.error('Unrecognized type category:', category);
        }
        $.each(attributeTypes, function(attrNo, attr) {
          var $input = $('#'+category+'_attr_'+Util.escapeQuotes(attr.type));
          if (attr.bool) {
            attributes[attr.type] = $input[0].checked;
          } else if ($input[0].selectedIndex) {
            attributes[attr.type] = $input.val();
          }
        });
        return attributes;
      }

      var spanAndAttributeTypesLoaded = function(_spanTypes, 
                                                 _entityAttributeTypes,
                                                 _eventAttributeTypes,
                                                 _relationTypesHash) {
        spanTypes = _spanTypes;
        entityAttributeTypes = _entityAttributeTypes;
        eventAttributeTypes = _eventAttributeTypes;
        relationTypesHash = _relationTypesHash;
      };

      var gotCurrent = function(_coll, _doc, _args) {
        coll = _coll;
        doc = _doc;
        args = _args;
      };

      var undoStack = [];
      var edited = function(response) {
        var x = response.exception;
        if (x) {
          if (x == 'annotationIsReadOnly') {
            dispatcher.post('messages', [[["This document is read-only and can't be edited.", 'error']]]);
          } else if (x == 'spanOffsetOverlapError') {
            // createSpan with overlapping frag offsets; reset offsets
            // @amadanmath: who holds the list of offsets for a span?
            // how to reset this?
          } else {
            dispatcher.post('messages', [[['Unknown error '+x, 'error']]]);
          }
          if (reselectedSpan) {
            $(reselectedSpan.rect).removeClass('reselect');
            reselectedSpan = null;
          }
          svgElement.removeClass('reselect');
          $('#waiter').dialog('close');
        } else {
          if (response.edited == undefined) {
            console.warn('Warning: server response to edit has', response.edited, 'value for "edited"');
          } else {
            args.edited = response.edited;
          }
          var sourceData = response.annotations;
          sourceData.document = doc;
          sourceData.collection = coll;
          // this "prevent" is to protect against reloading (from the
          // server) the very data that we just received as part of the
          // response to the edit.
          if (response.undo != undefined) {
            undoStack.push([coll, sourceData.document, response.undo]);
          }
          dispatcher.post('preventReloadByURL');
          dispatcher.post('setArguments', [args]);
          dispatcher.post('renderData', [sourceData]);
        }
      };


      // TODO: why are these globals defined here instead of at the top?
      var spanForm = $('#span_form');
      var rapidSpanForm = $('#rapid_span_form');
    
      var deleteSpan = function() {
        if (Configuration.confirmModeOn && !confirm("Are you sure you want to delete this annotation?")) {
          return;
        }
        $.extend(spanOptions, {
          action: 'deleteSpan',
          collection: coll,
          'document': doc,
        });
        spanOptions.offsets = JSON.stringify(spanOptions.offsets);
        dispatcher.post('ajax', [spanOptions, 'edited']);
        dispatcher.post('hideForm');
        $('#waiter').dialog('open');
      };

      var reselectSpan = function() {
        dispatcher.post('hideForm');
        svgElement.addClass('reselect');
        $(editedSpan.rect).addClass('reselect');
        reselectedSpan = editedSpan;
        selectedFragment = null;
      };

      var splitForm = $('#split_form');
      splitForm.submit(function(evt) {
        var splitRoles = [];
        $('#split_roles input:checked').each(function() {
          splitRoles.push($(this).val());
        });
        $.extend(spanOptions, {
            action: 'splitSpan',
            'args': $.toJSON(splitRoles),
            collection: coll,
            'document': doc,
          });
        spanOptions.offsets = JSON.stringify(spanOptions.offsets);
        dispatcher.post('hideForm');
        dispatcher.post('ajax', [spanOptions, 'edited']);
        return false;
      });
      dispatcher.post('initForm', [splitForm, {
          alsoResize: '.scroll_fset',
          width: 400,
          open: function() {
            $('#split_form-ok').focus();
          }
        }]);
      var splitSpan = function() {
        dispatcher.post('hideForm');
        var $roles = $('#split_roles').empty();
        var numRoles = repeatingArcTypes.length;
        var roles = $.each(repeatingArcTypes, function() {
          var $role = $('<input id="split_on_' + Util.escapeQuotes(this) +
            '" type="checkbox" name="' + Util.escapeQuotes(this) +
            '" value="' + Util.escapeQuotes(this) + '"/>');
          if (numRoles == 1) {
            // a single role will be selected automatically
            $role.click();
          }
          var $label = $('<label for="split_on_' + Util.escapeQuotes(this) +
            '">' + Util.escapeQuotes(this) + '</label>');
          $roles.append($role).append($label);
        });
        var $roleButtons = $roles.find('input').button();
        
        dispatcher.post('showForm', [splitForm]);
      };

      var addFragment = function() {
        dispatcher.post('hideForm');
        svgElement.addClass('reselect');
        $(editedSpan.rect).addClass('reselect');
        reselectedSpan = editedSpan;
        selectedFragment = false;
      };

      var reselectFragment = function() {
        addFragment();
        selectedFragment = editedFragment;
      };

      var deleteFragment = function() {
        if (Configuration.confirmModeOn && !confirm("Are you sure you want to delete this fragment?")) {
          return;
        }
        var offsets = editedSpan.offsets;
        spanOptions.old_offsets = JSON.stringify(offsets);
        offsets.splice(editedFragment, 1);

        $.extend(spanOptions, {
          collection: coll,
          'document': doc,
          offsets: JSON.stringify(offsets),
        });

        spanOptions.attributes = $.toJSON(spanAttributes());

        spanOptions.normalizations = $.toJSON(spanNormalizations());

        dispatcher.post('ajax', [spanOptions, 'edited']);
        dispatcher.post('hideForm');
        $('#waiter').dialog('open');
      };

      var spanChangeLock = function(evt) {
        var $this = $(evt.target);
        var locked = $this.is(':checked');
        $(evt.target).button('option', 'icons', {
          primary: locked ? 'ui-icon-locked' : 'ui-icon-unlocked'
        });
        $('#unlock_type_button').toggle(locked);
        if (!locked) lockOptions = null;
      };
      $('#unlock_type_button').button().hide().click(function(evt) {
        setTypeLock(false);
      });

      dispatcher.post('initForm', [spanForm, {
          alsoResize: '#entity_and_event_wrapper',
          width: 760,
          buttons: [{
              id: 'span_form_add_fragment',
              text: "Add Frag.",
              click: addFragment
            }, {
              id: 'span_form_delete',
              text: "Delete",
              click: deleteSpan
            }, {
              id: 'span_form_delete_fragment',
              text: "Delete Frag.",
              click: deleteFragment
            }, {
              id: 'span_form_reselect',
              text: 'Move',
              click: reselectSpan
            }, {
              id: 'span_form_reselect_fragment',
              text: 'Move Frag.',
              click: reselectFragment
            }, {
              id: 'span_form_split',
              text: 'Split',
              click: splitSpan
            }
          ],
          create: function(evt) {
            var $ok = $('#span_form-ok').wrap('<span id="span_form_lock_bset"/>');
            var $span = $ok.parent();
            var $lock = $('<input id="span_form_lock" type="checkbox"/>').insertBefore($ok);
            $('<label for="span_form_lock"/>').text("Lock type").insertBefore($ok);
            $lock.button({
              id: 'span_form_lock',
              text: false,
              icons: {
                primary: 'ui-icon-unlocked'
              },
            });
            $lock.click(spanChangeLock);
            $($span).buttonset();
          },
          beforeClose: function(evt) {
            // in case the form is cancelled
            setTypeLock(!!lockOptions);
          },
          close: function(evt) {
            keymap = null;
            if (reselectedSpan) {
              $(reselectedSpan.rect).removeClass('reselect');
              reselectedSpan = null;
              svgElement.removeClass('reselect');
            }
          }
        }]);
      // set button tooltips (@amadanmath: can this be done in init?)
      $('#span_form_reselect').attr('title', 'Re-select the text span that this annotation marks.');
      $('#span_form_delete').attr('title', 'Delete this annotation.');
      $('#span_form_split').attr('title', 'Split this annotation into multiple similar annotations, distributing its arguments.');

      var setTypeLock = function(val) {
        $('#span_form_lock').prop('checked', val).button('refresh');
        $('#unlock_type_button').toggle(val);
        if (!val) lockOptions = null;
      };

      dispatcher.post('initForm', [rapidSpanForm, {
          alsoResize: '#rapid_span_types',
          width: 400,             
          close: function(evt) {
            keymap = null;
          }
        }]);

      var spanFormSubmit = function(evt, typeRadio) {
        typeRadio = typeRadio || $('#span_form input:radio:checked');
        var type = typeRadio.val();
        $('#span_form-ok').blur();

        var locked = $('#span_form_lock').is(':checked');
        if (locked && !lockOptions) {
          lockOptions = {
            type: type
          }
        }

        dispatcher.post('hideForm');
        $.extend(spanOptions, {
          action: 'createSpan',
          collection: coll,
          'document': doc,
          type: type,
          comment: $('#span_notes').val()
        });

        spanOptions.attributes = $.toJSON(spanAttributes());

        spanOptions.normalizations = $.toJSON(spanNormalizations());

        if (spanOptions.offsets) {
          spanOptions.offsets = $.toJSON(spanOptions.offsets);
        }

        if (lockOptions) {
          $.extend(spanOptions, lockOptions);
        }

        // unfocus all elements to prevent focus being kept after
        // hiding them
        spanForm.parent().find('*').blur();

        $('#waiter').dialog('open');
        dispatcher.post('ajax', [spanOptions, 'edited']);
        return false;
      };
      $('#span_notes').focus(function () {
          keymap = null;
        }).blur(function () {
          keymap = spanKeymap;
        });
      spanForm.submit(spanFormSubmit);

      var rapidSpanFormSubmit = function(evt, typeRadio) {
        typeRadio = typeRadio || $('#rapid_span_form input:radio:checked');
        var type = typeRadio.val();

        // unfocus all elements to prevent focus being kept after
        // hiding them
        rapidSpanForm.parent().find('*').blur();
        dispatcher.post('hideForm');

        if (type == "") {
          // empty type value signals the special case where the user
          // selected "none of the above" of the proposed types and
          // the normal dialog should be brought up for the same span.
          spanOptions = {
            action: 'createSpan',
            offsets: rapidSpanOptions.offsets,
          };
          // TODO: avoid using the stored mouse event
          fillSpanTypesAndDisplayForm(lastRapidAnnotationEvent,
                                      $('#rapid_span_selected').text());
          dispatcher.post('logAction', ['normalSpanSelected']);
        } else {
          // normal type selection; submit createSpan with the selected type.
          $.extend(rapidSpanOptions, {
            action: 'createSpan',
            collection: coll,
            'document': doc,
            type: type,
          });
          $('#waiter').dialog('open');
          rapidSpanOptions.offsets = JSON.stringify(rapidSpanOptions.offsets);
          dispatcher.post('ajax', [rapidSpanOptions, 'edited']);
        }
        return false;
      };
      rapidSpanForm.submit(rapidSpanFormSubmit);

      var importForm = $('#import_form');
      var importFormSubmit = function(evt) {
        var _docid = $('#import_docid').val();
        var _doctext = $('#import_text').val();
        var opts = {
          action : 'importDocument',
          collection : coll,
          docid  : _docid,
          text  : _doctext,
        };
        dispatcher.post('ajax', [opts, function(response) {
          var x = response.exception;
          if (x) {
            if (x == 'fileExistsError') {
              dispatcher.post('messages', [[["A file with the given name exists. Please give a different name to the file to import.", 'error']]]);
            } else {
              dispatcher.post('messages', [[['Unknown error: ' + response.exception, 'error']]]);
            }
          } else {
            dispatcher.post('hideForm');
            dispatcher.post('setDocument', [response.document]);
          }
        }]);
        return false;
      };
      importForm.submit(importFormSubmit);
      dispatcher.post('initForm', [importForm, {
          width: 500,
          alsoResize: '#import_text',
          open: function(evt) {
            keymap = {};
          },
        }]);
      $('#import_button').click(function() {
        dispatcher.post('hideForm');
        dispatcher.post('showForm', [importForm]);
        importForm.find('input, textarea').val('');
      });

      var importCollForm = $('#import_coll_form');
      var importCollDone = function() {
        // TODO
      };
      var importCollFormSubmit = function(evt) {
        var data = new FormData(importCollForm[0]);
        data.append('action', 'upload_collection')
        dispatcher.post('ajax', [data, importCollDone, undefined, {
          cache: false,
          contentType: false,
          processData: false,
        }]);
        return false;
      };
      importCollForm.submit(importCollFormSubmit);
      dispatcher.post('initForm', [importCollForm, {
          width: 500,
          open: function(evt) {
            keymap = {};
          },
        }]);
      $('#import_collection_button').click(function() {
        dispatcher.post('hideForm');
        dispatcher.post('showForm', [importCollForm]);
        importCollForm.find('input').val('');
      });


      /* BEGIN delete button - related */

      $('#delete_document_button').click(function() {
        if (!doc) {
          dispatcher.post('messages', [[['No document selected', 'error']]]);
          return false;
        }
        if (!confirm('Are you sure you want to permanently remove this document and its annotations from the collection? This action cannot be undone.')) {
          return;
        }
        var delOptions = {
          action: 'deleteDocument',
          collection: coll,
          'document': doc
        }
        dispatcher.post('ajax', [delOptions, 'docDeleted']);
      });

      $('#delete_collection_button').click(function() {
        if (!coll) {
          dispatcher.post('messages', [[['No collection selected', 'error']]]);
          return false;
        }
        if (!confirm('Are you sure you want to permanently REMOVE the ENTIRE COLLECTION '+coll+', including all its documents and their annotations?  This action CANNOT BE UNDONE.')) {
          return;
        }
        var delOptions = {
          action: 'deleteCollection',
          collection: coll,
        }
        dispatcher.post('ajax', [delOptions, 'collDeleted']);
      });

      /* END delete button - related */

      $('#undo_button').click(function() {
        if (coll && doc) {
          if (undoStack.length > 0) {
            var storedUndo = undoStack.pop();
            var collection = storedUndo[0];
            var dok = storedUndo[1];
            var token = storedUndo[2];
            var options = {
              'action': 'undo',
              'collection': collection,
              'document': dok,
              'token': token
            }
            dispatcher.post('ajax', [options, 'edited']);
          } else {
            dispatcher.post('messages', [[['No action to be undone', 'error']]]);
          }
        } else {
          dispatcher.post('messages', [[['No document loaded, can not undo changes', 'error']]]);
        }
      });


      var preventDefault = function(evt) {
        evt.preventDefault();
      }

      var $waiter = $('#waiter');
      $waiter.dialog({
        closeOnEscape: false,
        buttons: {},
        modal: true,
        open: function(evt, ui) {
          $(evt.target).parent().find(".ui-dialog-titlebar-close").hide();
        }
      });
      // hide the waiter (Sampo said it's annoying)
      // we don't elliminate it altogether because it still provides the
      // overlay to prevent interaction
      $waiter.parent().css('opacity', '0');

      var isReloadOkay = function() {
        // do not reload while the user is in the middle of editing
        return arcDragOrigin == null && reselectedSpan == null;
      };

      var userReceived = function(_user) {
        that.user = _user;
      }

      var setAnnotationSpeed = function(speed) {
        if (speed == 1) {
          Configuration.confirmModeOn = true;
        } else {
          Configuration.confirmModeOn = false;
        }
        if (speed == 3) {
          Configuration.rapidModeOn = true;
        } else {
          Configuration.rapidModeOn = false;
        }
        dispatcher.post('configurationChanged');
      };

      var onNewSourceData = function(_sourceData) {
        sourceData = _sourceData;
      }

      var init = function() {
        dispatcher.post('annotationIsAvailable');
      };

      var arcDragArcDrawn = function(arc) {
        arcDragArc = arc;
      };

      dispatcher.
          on('init', init).
          on('arcDragArcDrawn', arcDragArcDrawn).
          on('getValidArcTypesForDrag', getValidArcTypesForDrag).
          on('dataReady', rememberData).
          on('collectionLoaded', rememberSpanSettings).
          on('collectionLoaded', setupTaggerUI).
          on('collectionLoaded', setupNormalizationUI).
          on('spanAndAttributeTypesLoaded', spanAndAttributeTypesLoaded).
          on('newSourceData', onNewSourceData).
          on('showForm', showForm).
          on('hideForm', hideForm).
          on('user', userReceived).
          on('edited', edited).
          on('current', gotCurrent).
          on('isReloadOkay', isReloadOkay).
          on('keydown', onKeyDown).
          on('dblclick', onDblClick).
          on('dragstart', preventDefault).
          on('mousedown', onMouseDown).
          on('mouseup', onMouseUp).
          on('mousemove', onMouseMove).
          on('annotationSpeed', setAnnotationSpeed).
          on('suggestedSpanTypes', receivedSuggestedSpanTypes).
          on('normGetNameResult', setSpanNormText).
          on('normSearchResult', setSpanNormSearchResults);
    };

    return AnnotatorUI;
})(jQuery, window);
