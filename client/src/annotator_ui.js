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
      var rapidSpanOptions = null;
      var arcOptions = null;
      var spanKeymap = null;
      var keymap = null;
      var coll = null;
      var doc = null;
      var reselectedSpan = null;
      var editedSpan = null;
      var repeatingArcTypes = [];
      var spanTypes = null;
      var entityAttributeTypes = null;
      var eventAttributeTypes = null;
      var allAttributeTypes = null; // TODO: temp workaround, remove
      var relationTypesHash = null;
      var showValidAttributes; // callback function
      var dragStartedAt = null;
      var selRect = null;
      var lastStartRec = null;
      var lastEndRec = null;

      var draggedArcHeight = 30;
      var spanTypesToShowBeforeCollapse = 30;

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
      // for normalization
      var oldSpanNormIdValue = '';

      that.user = null;
      var svgElement = $(svg._svg);
      var svgId = svgElement.parent().attr('id');

      var hideForm = function() {
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
          stopArcDrag();
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

        if (!keymap) return;

        // disable shortcuts when working with elements that you could
        // conceivably type in
        var target = evt.target;
        var nodeName = target.nodeName.toLowerCase();
        var nodeType = target.type && target.type.toLowerCase();
        if (nodeName == 'input' && (nodeType == 'text' || nodeType == 'password')) return;
        if (nodeName == 'textarea' || nodeName == 'select') return;

        var binding = keymap[code];
        if (!binding) binding = keymap[String.fromCharCode(code)];
        if (binding) {
          var boundInput = $('#' + binding)[0];
          if (boundInput && !boundInput.disabled) {
            boundInput.click();
          }
        }
        return false;
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
            if (eventDesc.equiv) {
              arcOptions['left'] = eventDesc.leftSpans.join(',');
              arcOptions['right'] = eventDesc.rightSpans.join(',');
            }
          }
          $('#arc_origin').text(Util.spanDisplayForm(spanTypes, originSpan.type) + ' ("' + data.text.substring(originSpan.from, originSpan.to) + '")');
          $('#arc_target').text(Util.spanDisplayForm(spanTypes, targetSpan.type) + ' ("' + data.text.substring(targetSpan.from, targetSpan.to) + '")');
          var arcId = originSpanId + '--' + type + '--' + targetSpanId; // TODO
          var arcAnnotatorNotes = ''; // TODO fill from info to be provided by server
          fillArcTypesAndDisplayForm(evt, originSpan.type, targetSpan.type, type, arcId, arcAnnotatorNotes);
          // for precise timing, log dialog display to user.
          dispatcher.post('logAction', ['arcEditSelected']);

        // if not an arc, then do we edit a span?
        } else if (id = target.attr('data-span-id')) {
          clearSelection();
          editedSpan = data.spans[id];
          spanOptions = {
            action: 'createSpan',
            start: editedSpan.from,
            end: editedSpan.to,
            type: editedSpan.type,
            id: id,
          };
          var spanText = data.text.substring(editedSpan.from, editedSpan.to);
          fillSpanTypesAndDisplayForm(evt, spanText, editedSpan);
          // for precise timing, log annotation display to user.
          dispatcher.post('logAction', ['spanEditSelected']);
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
        clearSelection();
        svgPosition = svgElement.offset();
        arcDragOrigin = originId;
        arcDragArc = svg.path(svg.createPath(), {
          markerEnd: 'url(#drag_arrow)',
          'class': 'drag_stroke',
          fill: 'none',
        });
        arcDragOriginGroup = $(data.spans[arcDragOrigin].group);
        arcDragOriginGroup.addClass('highlight');
        arcDragOriginBox = Util.realBBox(data.spans[arcDragOrigin]);
        arcDragOriginBox.center = arcDragOriginBox.x + arcDragOriginBox.width / 2;

        arcDragJustStarted = true;
      };

      var getValidArcTypesForDrag = function(targetId, targetType) {
        if (!arcDragOrigin || targetId == arcDragOrigin) return null;

        var originType = data.spans[arcDragOrigin].type;
        var spanType = spanTypes[originType];
        var result = [];
        if (spanType) {
          $.each(spanType.arcs, function(arcNo, arc) {
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
          return false;
        }
      };

      var onMouseMove = function(evt) {
        if (arcDragOrigin) {
          if (arcDragJustStarted) {
            // show the possible targets
            var span = data.spans[arcDragOrigin] || {};
            var spanDesc = spanTypes[span.type] || {};
            // var targetClasses = [];
            var $targets = $();
            $.each(spanDesc.arcs || [], function(possibleArcNo, possibleArc) {
              $.each(possibleArc.targets || [], function(possibleTargetNo, possibleTarget) {
                // speedup for #642: relevant browsers should support
                // this function: http://www.quirksmode.org/dom/w3c_core.html#t11
                // so we get off jQuery and get down to the metal:
                // targetClasses.push('.span_' + possibleTarget);
                $targets = $targets.add(svgElement[0].getElementsByClassName('span_' + possibleTarget));
              });
            });
            // $(targetClasses.join(',')).not('[data-span-id="' + arcDragOrigin + '"]').addClass('reselectTarget');
            $targets.not('[data-span-id="' + arcDragOrigin + '"]').addClass('reselectTarget');
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

        // close span types if there's over spanTypesToShowBeforeCollapse
        if ($('#entity_types .item').length > spanTypesToShowBeforeCollapse) {
          $('#entity_types .open').removeClass('open');
        }
        if ($('#event_types .item').length > spanTypesToShowBeforeCollapse) {
          $('#event_types .open').removeClass('open');
        }

        var showAllAttributes = false;
        if (span) {
          var urlHash = URLHash.parse(window.location.hash);
          urlHash.setArgument('focus', [[span.id]]);
          $('#span_highlight_link').show().attr('href', urlHash.getHash());
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
          $('#span_highlight_link').hide();
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
        if (span && !reselectedSpan) {
          $('#span_form_reselect, #span_form_delete').show();
          keymap[$.ui.keyCode.DELETE] = 'span_form_delete';
          keymap[$.ui.keyCode.INSERT] = 'span_form_reselect';
          $('#span_notes').val(span.annotatorNotes || '');
        } else {
          $('#span_form_reselect, #span_form_delete').hide();
          keymap[$.ui.keyCode.DELETE] = null;
          keymap[$.ui.keyCode.INSERT] = null;
        }
        if (!reselectedSpan) {
          // TODO: avoid allAttributeTypes; just check type-appropriate ones
          $.each(allAttributeTypes, function(attrNo, attr) {
            $input = $('#span_attr_' + Util.escapeQuotes(attr.type));
            var val = span && span.attributes[attr.type];
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

        // fill normalizations (if any)
        if (!reselectedSpan) {
          // clear first
          clearNormalizationUI();

          var $normDb = $('#span_norm_db');
          var $normId = $('#span_norm_id');
          var $normText = $('#span_norm_txt');

          // fill if found (NOTE: only shows last on multiple)
          $.each(span ? span.normalizations : [], function(normNo, norm) {
            // stored as array (sorry)
            var refDb = norm[0], refId = norm[1], refText = norm[2];
            $normDb.val(refDb);
            $normId.val(refId);
            // don't forget to update this reference value
            oldSpanNormIdValue = refId
            $normText.val(refText);
            // just assume the ID is valid (TODO: check)
            $normId.addClass('valid_value')
          });

          // update links
          updateNormalizationRefLink();
          updateNormalizationDbLink();
        }

        var showAttributesFor = function(attrTypes, type) {
          var validAttrs = type ? spanTypes[type].attributes : [];
          var shownCount = 0;
          $.each(attrTypes, function(attrNo, attr) {
            var $input = $('#span_attr_' + Util.escapeQuotes(attr.type));
            var showAttr = showAllAttributes || $.inArray(attr.type, validAttrs) != -1;
            if (showAttr) {
              $input.button('widget').show();
              shownCount++;
            } else {
              $input.button('widget').hide();
            }
          });
          return shownCount;
        }

        showValidAttributes = function() {
          var type = $('#span_form input:radio:checked').val();
          var entityAttrCount = showAttributesFor(entityAttributeTypes, type);
          var eventAttrCount = showAttributesFor(eventAttributeTypes, type);
          
          showAllAttributes = false;
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
          if (reselectedSpan) {
            $(reselectedSpan.rect).removeClass('reselect');
          }
          reselectedSpan = null;
          spanForm.submit();
        } else {
          dispatcher.post('showForm', [spanForm]);
          $('#span_form-ok').focus();
          adjustToCursor(evt, spanForm.parent());
        }
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

      var clearSpanNotes = function(evt) {
        $('#span_notes').val('');
      }
      $('#clear_notes_button').button();
      $('#clear_notes_button').click(clearSpanNotes);

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
        var $idinput = $('#span_norm_id');
        // TODO: make sure the key echo in the response matches the
        // current value of the $idinput
        $idinput.removeClass('valid_value').removeClass('invalid_value');
        if (response.value === null) {
          $idinput.addClass('invalid_value');
          hideNormalizationRefLink();
        } else {
          $idinput.addClass('valid_value');
          updateNormalizationRefLink();
        }
        $('#span_norm_txt').val(response.value);
      }

      // on any change to the normalization DB, clear everything and
      // update link
      var spanNormDbUpdate = function(evt) {
        clearNormalizationUI();
        updateNormalizationDbLink();
      }
      $('#span_norm_db').change(spanNormDbUpdate);

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
                            key: key}, 'normGetNameResult']);
          }
          oldSpanNormIdValue = key;
        }
      }
      // see http://stackoverflow.com/questions/1948332/detect-all-changes-to-a-input-type-text-immediately-using-jquery
      $('#span_norm_id').bind('propertychange keyup input paste', spanNormIdUpdate);
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
            dispatcher.post('showForm', [spanForm]);
          },
      });
      var normSearchSubmit = function(evt) {
        var selectedId = $('#norm_search_id').val(); 
        var selectedTxt = $('#norm_search_query').val();
        if (normSearchSubmittable) {
          // we got a value; act if it was a submit
          $('#span_norm_id').val(selectedId);
          // don't forget to update this reference value
          oldSpanNormIdValue = selectedId;
          $('#span_norm_txt').val(selectedTxt);
          updateNormalizationRefLink();
          // Switch dialogs. NOTE: assuming we closed the spanForm when
          // bringing up the normSearchDialog.
          normSearchDialog.dialog('close');
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
          html.push('<tr'+
                    ' data-id="'+Util.escapeHTML(item[0])+'"'+
                    ' data-txt="'+Util.escapeHTML(item[1])+'"'+
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
                        name: val}, 'normSearchResult']);
      }
      $('#norm_search_button').click(performNormSearch);
      $('#norm_search_query').focus(function() {
        setNormSearchSubmit(false);
      });
      var showNormSearchDialog = function() {
        // if we already have non-empty ID and normalized string,
        // use these as default; otherwise take default search string
        // from annotated span and clear ID entry
        if (!$('#span_norm_id').val().match(/^\s*$/) &&
            !$('#span_norm_txt').val().match(/^\s*$/)) {
            $('#norm_search_id').val($('#span_norm_id').val());
            $('#norm_search_query').val($('#span_norm_txt').val());
        } else {
            $('#norm_search_id').val('');
            $('#norm_search_query').val($('#span_selected').text());
        }
        // blank the table
        $('#norm_search_result_select thead').empty();
        $('#norm_search_result_select tbody').empty();        
        // TODO: support for two (or more) dialogs open at the same time
        // so we don't need to hide this before showing normSearchDialog
        dispatcher.post('hideForm');
        $('#norm_search_button').val('Search ' + $('#span_norm_db').val());
        setNormSearchSubmit(false);
        dispatcher.post('showForm', [normSearchDialog]);
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

      var fillArcTypesAndDisplayForm = function(evt, originType, targetType, arcType, arcId, arcAnnotatorNotes) {
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
          relationTypesHash[noNumArcType].properties.symmetric &&
          relationTypesHash[noNumArcType].properties.transitive;

        if (spanTypes[originType]) {
          var arcTypes = spanTypes[originType].arcs;
          var $scroller = $('#arc_roles .scroller').empty();

          // lay them out into the form
          $.each(arcTypes || [], function(arcTypeNo, arcDesc) {
            if (arcDesc.targets && arcDesc.targets.indexOf(targetType) != -1) {
              var arcTypeName = arcDesc.type;

              var isThisEquiv =
                relationTypesHash &&
                relationTypesHash[arcTypeName] &&
                relationTypesHash[arcTypeName].properties.symmetric &&
                relationTypesHash[arcTypeName].properties.transitive;

              // do not allow equiv<->non-equiv change options
              if (arcType && isEquiv != isThisEquiv) return;

              var displayName = ((arcDesc.labels && arcDesc.labels[0]) || 
                                 arcTypeName);
              var $checkbox = $('<input id="arc_' + arcTypeName + '" type="radio" name="arc_type" value="' + arcTypeName + '"/>');
              var $label = $('<label class="arc_type_label" for="arc_' + arcTypeName + '"/>').text(displayName);
              var $div = $('<div/>').append($checkbox).append($label);
              $scroller.append($div);
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

        if (arcId) {
          // something was selected
          $('#arc_highlight_link').attr('href', document.location + '/' + arcId).show(); // TODO incorrect
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

          arcForm.dialog('option', { title: 'Edit Annotation' });
        } else {
          // new arc
          $('#arc_highlight_link').hide();
          el = $('#arc_form input:radio:first')[0];
          if (el) {
            el.checked = true;
          }

          $('#arc_form_reselect, #arc_form_delete').hide();

          arcForm.dialog('option', { title: 'New Annotation' });
        }

        if (!Configuration.confirmModeOn) {
          arcForm.find('#arc_roles input:radio').click(arcFormSubmitRadio);
        }

        if (arcAnnotatorNotes) {
          $('#arc_notes').val(arcAnnotatorNotes);
        } else {
          $('#arc_notes').val('');
        }

        dispatcher.post('showForm', [arcForm]);
        $('#arc_form-ok').focus();
        adjustToCursor(evt, arcForm.parent());
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
          target.removeClass('badTarget');
          arcDragOriginGroup.removeClass('highlight');
          if (target) {
            target.parent().removeClass('highlight');
          }
          if (arcDragArc) {
            svg.remove(arcDragArc);
          }
          arcDragOrigin = null;
          if (arcOptions) {
              $('g[data-from="' + arcOptions.origin + '"][data-to="' + arcOptions.target + '"]').removeClass('reselect');
          }
          svgElement.removeClass('reselect');
        }
        $('.reselectTarget').removeClass('reselectTarget');
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

        // is it arc drag end?
        if (arcDragOrigin) {
          var origin = arcDragOrigin;
          stopArcDrag(target);
          if ((id = target.attr('data-span-id')) && origin != id) {
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
              $('#arc_origin').text(Util.spanDisplayForm(spanTypes, originSpan.type)+' ("'+data.text.substring(originSpan.from, originSpan.to)+'")');
              $('#arc_target').text(Util.spanDisplayForm(spanTypes, targetSpan.type)+' ("'+data.text.substring(targetSpan.from, targetSpan.to)+'")');
              fillArcTypesAndDisplayForm(evt, originSpan.type, targetSpan.type);
              // for precise timing, log dialog display to user.
              dispatcher.post('logAction', ['arcSelected']);
            }
          }
        } else if (!evt.ctrlKey) {
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

            if (reselectedSpan) {
              spanOptions.old_start = spanOptions.start;
              spanOptions.old_end = spanOptions.end;
            } else {
              spanOptions = {
                action: 'createSpan'
              }
            }

            $.extend(spanOptions, {
                start: selectedFrom,
                end: selectedTo
              });

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
          start: sugg.start,
          end: sugg.end,  
        };
        rapidFillSpanTypesAndDisplayForm(sugg.start, sugg.end, sugg.text, sugg.types);
      };

      var toggleCollapsible = function($el, state) {
        var opening = state !== undefined ? state : !$el.hasClass('open');
        var $collapsible = $el.parent().find('.collapsible:first');
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

      var spanFormSubmitRadio = function(evt) {
        if (Configuration.confirmModeOn) {
          showValidAttributes();
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
            var $collapser = $('<div class="collapser open"/>');
            var $div = $('<div class="item"/>');
            if (type.children.length) {
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
          var attrId = 'span_attr_' + escapedType;
          if (attr.unused) {
            var $input = $('<input type="hidden" id="'+attrId+'" value=""/>');
            $top.append($input);
          } else if (attr.bool) {
            var escapedName = Util.escapeQuotes(attr.name);
            var $input = $('<input type="checkbox" id="'+attrId+
                           '" value="' + escapedType + 
                           '" category="' + category + '"/>');
            var $label = $('<label class="attribute_type_label" for="'+attrId+
                           '" data-bare="' + escapedName + '">&#x2610; ' + 
                           escapedName + '</label>');
            $top.append($input).append($label);
            $input.button();
            $input.change(onBooleanAttrChange);
          } else {
            var $div = $('<div class="ui-button ui-button-text-only attribute_type_label"/>');
            var $select = $('<select id="'+attrId+'" class="ui-widget ui-state-default ui-button-text" category="' + category + '"/>');
            var $option = $('<option class="ui-state-default" value=""/>').text(attr.name + ': ?');
            $select.append($option);
            $.each(attr.values, function(valType, value) {
              $option = $('<option class="ui-state-active" value="' + Util.escapeQuotes(valType) + '"/>').text(attr.name + ': ' + (value.name || valType));
              $select.append($option);
            });
            $div.append($select);
            $top.append($div);
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
        $('#span_form input:not([unused])').removeAttr('disabled');
        var $toDisable;
        var $category;
        if (category == "event") {
          $toDisable = $('#span_form input[category="entity"]');
        } else if (category == "entity") {
          $toDisable = $('#span_form input[category="event"]');
        } else {
          console.error('Unrecognized attribute category:', category)
          $toDisable = $();
        }
        $toDisable.attr('disabled', true);
        // the disable may leave the dialog in a state where nothing
        // is checked, which would cause error on "OK". In this case,
        // check the first valid choice.
        if ($toDisable.is(':checked')) {
          $('#span_form input:not(:disabled):first').attr('checked', 'checked');
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
        var attrCategory = evt.target.getAttribute('category');
        setSpanTypeSelectability(attrCategory);
        updateCheckbox($(evt.target));
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
        spanForm.find('.collapser').click(collapseHandler);
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

      var setupNormalizationUI = function(response) {
        var norm_resources = response.normalization_config || [];
        var $norm_select = $('#span_norm_db');
        // clear possible existing
        $norm_select.empty();
        // fill in new
        html = [];
        $.each(norm_resources, function(normNo, norm) {
          var normName = norm[0], normUrl = norm[1], normUrlBase = norm[2];
          html.push('<option value="'+Util.escapeHTML(normName)+'">'+
                    Util.escapeHTML(normName)+'</option>');
          // remember the urls for updates
          normDbUrlByDbName[normName] = normUrl;
          normDbUrlBaseByDbName[normName] = normUrlBase;
        });
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
        if (!normId || normId.match(/^\s*$/)) {
          $normLink.hide();
        } else {
          var $normDb = $('#span_norm_db');
          var normDb = $normDb.val();
          var base = normDbUrlBaseByDbName[normDb];
          // assume hidden unless everything goes through
          $normLink.hide();
          if (!base) {
            dispatcher.post('messages', [[['No base URL for '+normDb, 'error']]]);
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

      // resets all normalization-related UI elements to a blank
      // state
      var clearNormalizationUI = function() {
        var $normId = $('#span_norm_id');
        var $normText = $('#span_norm_txt');
        $normId.val('');
        oldSpanNormIdValue = '';
        $normId.removeClass('valid_value').removeClass('invalid_value');
        $normText.val('');
        updateNormalizationRefLink();
      }

      var spanAndAttributeTypesLoaded = function(_spanTypes, 
                                                 _entityAttributeTypes,
                                                 _eventAttributeTypes,
                                                 _relationTypesHash) {
        spanTypes = _spanTypes;
        entityAttributeTypes = _entityAttributeTypes;
        eventAttributeTypes = _eventAttributeTypes;
        relationTypesHash = _relationTypesHash;
        // for easier access
        allAttributeTypes = $.extend({}, 
                                     entityAttributeTypes, 
                                     eventAttributeTypes);
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
        dispatcher.post('ajax', [spanOptions, 'edited']);
        dispatcher.post('hideForm');
        $('#waiter').dialog('open');
      };

      var reselectSpan = function() {
        dispatcher.post('hideForm');
        svgElement.addClass('reselect');
        $(editedSpan.rect).addClass('reselect');
        reselectedSpan = editedSpan;
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
        dispatcher.post('hideForm');
        dispatcher.post('ajax', [spanOptions, 'edited']);
        return false;
      });
      dispatcher.post('initForm', [splitForm, {
          alsoResize: '.scroll_fset',
          width: 400
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

      var linkSpan = function() {
        args.focus = [[spanOptions.id || spanOptions.start + '~' + spanOptions.end]];
        dispatcher.post('setArguments', [args]);
      };

      dispatcher.post('initForm', [spanForm, {
          alsoResize: '#entity_and_event_wrapper',
          width: 760,
          buttons: [{
              id: 'span_form_link',
              text: "Link",
              click: linkSpan
            }, {
              id: 'span_form_delete',
              text: "Delete",
              click: deleteSpan
            }, {
              id: 'span_form_reselect',
              text: 'Move',
              click: reselectSpan
            }, {
              id: 'span_form_split',
              text: 'Split',
              click: splitSpan
          }],
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
      $('#span_form_link').attr('title', 'Mark the span, and generate the URL that can be copied.');

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
        dispatcher.post('hideForm');
        $.extend(spanOptions, {
          action: 'createSpan',
          collection: coll,
          'document': doc,
          type: type,
          comment: $('#span_notes').val()
        });

        // fill attributes
        var attributes = {};
        // TODO: avoid allAttributeTypes; just check type-appropriate ones
        $.each(allAttributeTypes, function(attrNo, attr) {
          var $input = $('#span_attr_' + Util.escapeQuotes(attr.type));
          if (attr.bool) {
            attributes[attr.type] = $input[0].checked;
          } else if ($input[0].selectedIndex) {
            attributes[attr.type] = $input.val();
          }
        });
        spanOptions.attributes = $.toJSON(attributes);

        // fill normalizations. Note that the protocol supports any
        // number, but only no or one normalization supported in UI at
        // the moment.
        var normalizations = [];
        var normDb = $('#span_norm_db').val();
        var normId = $('#span_norm_id').val();
        var normText = $('#span_norm_txt').val();
        // empty ID -> no normalization
        if (!normId.match(/^\s*$/)) {
          normalizations.push([normDb, normId, normText]);
        }
        spanOptions.normalizations = $.toJSON(normalizations);

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
            start: rapidSpanOptions.start,
            end: rapidSpanOptions.end,
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
          dispatcher.post('ajax', [rapidSpanOptions, 'edited']);
        }
        return false;
      };
      rapidSpanForm.submit(rapidSpanFormSubmit);

      var importForm = $('#import_form');
      var importFormSubmit = function(evt) {
        var _docid = $('#import_docid').val();
        var _doctitle = $('#import_title').val();
        var _doctext = $('#import_text').val();
        var opts = {
          action : 'importDocument',
          collection : coll,
          docid  : _docid,
          title : _doctitle,
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

      dispatcher.
          on('init', init).
          on('getValidArcTypesForDrag', getValidArcTypesForDrag).
          on('dataReady', rememberData).
          on('collectionLoaded', rememberSpanSettings).
          on('collectionLoaded', setupTaggerUI).
          on('collectionLoaded', setupNormalizationUI).
          on('spanAndAttributeTypesLoaded', spanAndAttributeTypesLoaded).
          on('newSourceData', onNewSourceData).
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
