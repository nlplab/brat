// -*- Mode: JavaScript; tab-width: 2; indent-tabs-mode: nil; -*-
// vim:set ft=javascript ts=2 sw=2 sts=2 cindent:
var AnnotatorUI = (function($, window, undefined) {
    var AnnotatorUI = function(dispatcher, svg) {
      var that = this;
      var arcDragOrigin = null;
      var arcDragOriginBox = null;
      var arcDragOriginGroup = null;
      var arcDragArc = null;
      var data = null;
      var searchConfig = null;
      var spanOptions = null;
      var arcOptions = null;
      var spanKeymap = null;
      var keymap = null;
      var coll = null;
      var doc = null;
      var reselectedSpan = null;
      var editedSpan = null;
      var repeatingArcTypes = [];
      var spanTypes = null;
      var attributeTypes = null;
      var showValidAttributes; // callback function

      // amount by which to lighten (adjust "L" in HSL space) span
      // colors for type selection box BG display. 0=no lightening,
      // 1=white BG (no color)
      var spanBoxTextBgColorLighten = 0.4;

      that.user = null;
      var svgElement = $(svg._svg);
      var svgId = svgElement.parent().attr('id');

      var hideForm = function() {
        keymap = null;
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
          $('#' + binding).click();
        }
        return false;
      };

      var onDblClick = function(evt) {
        if (that.user === null) return;
        var target = $(evt.target);
        var id;
        // do we edit an arc?
        if (id = target.attr('data-arc-role')) {
          // TODO
          window.getSelection().removeAllRanges();
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

        // if not, then do we edit a span?
        } else if (id = target.attr('data-span-id')) {
          window.getSelection().removeAllRanges();
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
        }
      };

      var startArcDrag = function(originId) {
        window.getSelection().removeAllRanges();
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
      };

      var onMouseDown = function(evt) {
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
          window.getSelection().removeAllRanges();
          var mx = evt.pageX - svgPosition.left;
          var my = evt.pageY - svgPosition.top + 5; // TODO FIXME why +5?!?
          var y = Math.min(arcDragOriginBox.y, my) - 50;
          var dx = (arcDragOriginBox.center - mx) / 4;
          var path = svg.createPath().
            move(arcDragOriginBox.center, arcDragOriginBox.y).
            curveC(arcDragOriginBox.center - dx, y,
                mx + dx, y,
                mx, my);
          arcDragArc.setAttribute('d', path.path());
        }
      };

      var adjustToCursor = function(evt, element) {
        var screenHeight = $(window).height() - 8; // TODO HACK - no idea why -8 is needed
        var screenWidth = $(window).width() - 8;
        var elementHeight = element.height();
        var elementWidth = element.width();
        var y = Math.min(evt.clientY, screenHeight - elementHeight);
        var x = Math.min(evt.clientX, screenWidth - elementWidth);
        element.css({ top: y, left: x });
      };

      var updateCheckbox = function($input) {
        var $widget = $input.button('widget');
        var $textspan = $widget.find('.ui-button-text');
        $textspan.text(($input[0].checked ? '☑ ' : '☐ ') + $widget.attr('data-bare'));
      };

      var fillSpanTypesAndDisplayForm = function(evt, spanText, span) {
        keymap = spanKeymap;
        if (span) {
          $('#del_span_button').show();
          if (span.generalType == 'entity') { // entity
            $('#event_types').hide()
            $('#entity_types').show().removeClass('scroll_wrapper_half').addClass('scroll_wrapper_full');
          } else { // trigger
            $('#entity_types').hide();
            $('#event_types').show().removeClass('scroll_wrapper_half').addClass('scroll_wrapper_full');
          }
        } else {
          $('#del_span_button').hide();
          $('#entity_types, #event_types').show().removeClass('scroll_wrapper_full').addClass('scroll_wrapper_half');
        }
        $('#span_selected').text(spanText);
        var encodedText = encodeURIComponent(spanText);       
        $.each(searchConfig, function(searchNo, search) {
          $('#span_'+search[0]).attr('href', search[1].replace('%s', encodedText));
        });
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

          // count the repeating arc types
          var arcTypeCount = {};
          repeatingArcTypes = [];
          $.each(span.outgoing, function(arcNo, arc) {
            if ((arcTypeCount[arc.type] = (arcTypeCount[arc.type] || 0) + 1) == 2) {
              repeatingArcTypes.push(arc.type);
            }
          });
          if (repeatingArcTypes.length) {
            $('#span_form_split').show();
          } else {
            $('#span_form_split').hide();
          }
        } else {
          $('#span_highlight_link').hide();
          var firstRadio = $('#span_form input:radio:first')[0];
          if (firstRadio) {
            firstRadio.checked = true;
          } else {
            dispatcher.post('hideForm', [spanForm]);
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
          $('#span_notes').val(span.annotatorNotes || '');
        } else {
          $('#span_form_reselect, #span_form_delete').hide();
          keymap[$.ui.keyCode.DELETE] = null;
        }
        if (!reselectedSpan) {
          $.each(attributeTypes, function(attrNo, attr) {
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
        showValidAttributes = function() {
          var type = $('#span_form input:radio:checked').val();
          var validAttrs = type ? spanTypes[type].attributes : [];
          $.each(attributeTypes, function(attrNo, attr) {
            var $input = $('#span_attr_' + Util.escapeQuotes(attr.type));
            var showAttr = showAllAttributes || $.inArray(attr.type, validAttrs) != -1;
            if (showAttr) {
              $input.button('widget').show();
            } else {
              $input.button('widget').hide();
            }
          });
          showAllAttributes = false;
        }
        showValidAttributes();
        var confirmMode = $('#confirm_mode')[0].checked;
        if (reselectedSpan && !confirmMode) {
          spanForm.submit();
        } else {
          dispatcher.post('showForm', [spanForm]);
          $('#span_form-ok').focus();

          adjustToCursor(evt, spanForm.parent());
        }
      };

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

        if (spanTypes[originType]) {
          var arcTypes = spanTypes[originType].arcs;
          var $scroller = $('#arc_roles .scroller').empty();

          // lay them out into the form
          $.each(arcTypes || [], function(arcTypeNo, arcDesc) {
            if (arcDesc.targets && arcDesc.targets.indexOf(targetType) != -1) {
              var arcTypeName = arcDesc.type;
              var displayName = arcDesc.labels[0] || arcTypeName;
              var $checkbox = $('<input id="arc_' + arcTypeName + '" type="radio" name="arc_type" value="' + arcTypeName + '"/>');
              var $label = $('<label for="arc_' + arcTypeName + '"/>').text(displayName);
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
        } else {
          // new arc
          $('#arc_highlight_link').hide();
          el = $('#arc_form input:radio:first')[0];
          if (el) {
            el.checked = true;
          }

          $('#arc_form_reselect, #arc_form_delete').hide();
        }

        var confirmMode = $('#confirm_mode')[0].checked;
        if (!confirmMode) {
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
        var confirmMode = $('#confirm_mode')[0].checked;
        if (confirmMode && !confirm("Are you sure you want to delete this annotation?")) {
          return;
        }
        var eventDataId = $(evt.target).attr('data-arc-ed');
        dispatcher.post('hideForm', [arcForm]);
        arcOptions.action = 'deleteArc';
        dispatcher.post('ajax', [arcOptions, 'edited']);
      };

      var reselectArc = function(evt) {
        dispatcher.post('hideForm', [arcForm]);
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

      var stopArcDrag = function(target) {
        if (arcDragOrigin) {
          arcDragOriginGroup.removeClass('highlight');
          if (target) {
            target.parent().removeClass('highlight');
          }
          svg.remove(arcDragArc);
          arcDragOrigin = null;
          if (arcOptions) {
              $('g[data-from="' + arcOptions.origin + '"][data-to="' + arcOptions.target + '"]').removeClass('reselect');
          }
          svgElement.removeClass('reselect');
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
          window.getSelection().removeAllRanges();
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
            }
          }
        } else if (!evt.ctrlKey) {
          // if not, then is it span selection? (ctrl key cancels)
          var sel = window.getSelection();
          var chunkIndexFrom = sel.anchorNode && $(sel.anchorNode.parentNode).attr('data-chunk-id');
          var chunkIndexTo = sel.focusNode && $(sel.focusNode.parentNode).attr('data-chunk-id');
          if (chunkIndexFrom !== undefined && chunkIndexTo !== undefined) {
            var chunkFrom = data.chunks[chunkIndexFrom];
            var chunkTo = data.chunks[chunkIndexTo];
            var selectedFrom = chunkFrom.from + sel.anchorOffset;
            var selectedTo = chunkTo.from + sel.focusOffset;
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
            $.each(data.sentence_offsets, function(sentNo, startEnd) {
              if (selectedTo <= startEnd[1]) {
                // this is the sentence

                if (selectedFrom >= startEnd[0]) {
                  crossSentence = false;
                }
                return false;
              }
            });

            if (crossSentence) {
              dispatcher.post('messages', [[['Error: cannot annotate across a sentence break', 'error']]]);
              $(reselectedSpan.rect).removeClass('reselect');
              reselectedSpan = null;
              svgElement.removeClass('reselect');
            } else {
              var spanText = data.text.substring(selectedFrom, selectedTo);
              fillSpanTypesAndDisplayForm(evt, spanText, reselectedSpan);
            }
          }
        }
      };

      var collapseHandler = function(evt) {
        var el = $(evt.target);
        var open = el.hasClass('open');
        var collapsible = el.parent().find('.collapsible').first();
        el.toggleClass('open');
        collapsible.toggleClass('open');
      };

      var spanFormSubmitRadio = function(evt) {
        var confirmMode = $('#confirm_mode')[0].checked;
        if (confirmMode) {
          showValidAttributes();
          $('#span_form-ok').focus();
        } else {
          spanFormSubmit(evt, $(evt.target));
        }
      }

      var rememberData = function(_data) {
        if (_data && !_data.exception) {
          data = _data;
        }
      };

      var addSpanTypesToDivInner = function($parent, types) {
        $.each(types, function(typeNo, type) {
          if (type === null) {
            $parent.append('<hr/>');
          } else {
            var name = type.name;
            var $input = $('<input type="radio" name="span_type"/>').
              attr('id', 'span_' + type.type).
              attr('value', type.type);
            // use a light version of the span color as BG
            var spanBgColor = spanTypes[type.type] && spanTypes[type.type].bgColor || '#ffffff';
            spanBgColor = Util.adjustColorLightness(spanBgColor, spanBoxTextBgColorLighten);
            var $label = $('<label/>').
              attr('for', 'span_' + type.type).
              text(name);
            if (type.unused) {
              $input.attr('disabled', 'disabled');
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
            addSpanTypesToDivInner($collapsible, type.children);
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

      var onAttributeChange = function(evt) {
        if (evt.target.selectedIndex) {
          $(evt.target).addClass('ui-state-active');
        } else {
          $(evt.target).removeClass('ui-state-active');
        }
      }

      var attrChangeHandler = function(evt) {
        updateCheckbox($(evt.target));
      };

      var rememberSpanSettings = function(response) {
        spanKeymap = {};

        // TODO: check for exceptions in response
        
        var $entities = $('<div id="entity_types" class="scroll_wrapper_half"/>');
        addSpanTypesToDiv($entities, response.entity_types, 'Entities');
        var $events = $('<div id="event_types" class="scroll_wrapper_half"/>');
        addSpanTypesToDiv($events, response.event_types, 'Events');
        $('#span_types').empty().append($entities).append($events);

        // hide event attributes box if not defined
        var $attrs = $('#span_attributes div.scroller').empty();
        $.each(attributeTypes, function(attrNo, attr) {
          var escapedType = Util.escapeQuotes(attr.type);
          if (attr.unused) {
            var $input = $('<input type="hidden" id="span_attr_' + escapedType + '" value=""/>');
            $attrs.append($input);
          } else if (attr.bool) {
            var escapedName = Util.escapeQuotes(attr.name);
            var $input = $('<input type="checkbox" id="span_attr_' + escapedType + '" value="' + escapedType + '"/>');
            var $label = $('<label for="span_attr_' + escapedType + '" data-bare="' + escapedName + '">&#x2610; ' + escapedName + '</label>');
            $attrs.append($input).append($label);
            $input.button();
            $input.change(attrChangeHandler);
          } else {
            var $div = $('<div class="ui-button ui-button-text-only"/>');
            var $select = $('<select id="span_attr_' + escapedType + '" class="ui-widget ui-state-default ui-button-text"/>');
            var $option = $('<option class="ui-state-default" value=""/>').text(attr.name + ': ?');
            $select.append($option);
            $.each(attr.values, function(valType, value) {
              $option = $('<option class="ui-state-active" value="' + Util.escapeQuotes(valType) + '"/>').text(attr.name + ': ' + (value.name || valType));
              $select.append($option);
            });
            $div.append($select);
            $attrs.append($div);
            $select.change(onAttributeChange);
          }
        });

        // fill search options in span dialog
        searchConfig = response.search_config;
        var $searchlinks  = $('#span_search_links').empty();
        var $searchlinks2 = $('#viewspan_search_links').empty();
        var firstLink=true;
        var linkFilled=false;
        $.each(searchConfig, function(searchNo, search) {
          if (!firstLink) {
            $searchlinks.append(',\n')
            $searchlinks2.append(',\n')
          }
          firstLink=false;
          $searchlinks.append('<a target="brat_search" id="span_'+search[0]+'" href="#">'+search[0]+'</a>');
          $searchlinks2.append('<a target="brat_search" id="viewspan_'+search[0]+'" href="#">'+search[0]+'</a>');
          linkFilled=true;
        });
        if (linkFilled) {
          $('#span_search_fieldset').show();
          $('#viewspan_search_fieldset').show();
        } else {
          $('#span_search_fieldset').hide();
          $('#viewspan_search_fieldset').hide();
        }

        spanForm.find('#span_types input:radio').click(spanFormSubmitRadio);
        spanForm.find('.collapser').click(collapseHandler);
      };

      var spanAndAttributeTypesLoaded = function(_spanTypes, _attributeTypes) {
        spanTypes = _spanTypes;
        attributeTypes = _attributeTypes;
      };

      var gotCurrent = function(_coll, _doc, _args) {
        coll = _coll;
        doc = _doc;
        args = _args;
      };

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
          data = response.annotations;
          data.document = doc;
          data.collection = coll;
          // this "prevent" is to protect against reloading (from the
          // server) the very data that we just received as part of the
          // response to the edit.
          dispatcher.post('preventReloadByURL');
          dispatcher.post('setArguments', [args]);
          dispatcher.post('renderData', [data]);
        }
      };


      var spanForm = $('#span_form');

      var deleteSpan = function() {
        var confirmMode = $('#confirm_mode')[0].checked;
        if (confirmMode && !confirm("Are you sure you want to delete this annotation?")) {
          return;
        }
        $.extend(spanOptions, {
          action: 'deleteSpan',
          collection: coll,
          'document': doc,
        });
        dispatcher.post('ajax', [spanOptions, 'edited']);
        dispatcher.post('hideForm', [spanForm]);
        $('#waiter').dialog('open');
      };

      var reselectSpan = function() {
        dispatcher.post('hideForm', [spanForm]);
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
        dispatcher.post('hideForm', [splitForm]);
        dispatcher.post('ajax', [spanOptions, 'edited']);
        return false;
      });
      dispatcher.post('initForm', [splitForm, {
          alsoResize: '.scroll_fset',
          width: 400
        }]);
      var splitSpan = function() {
        dispatcher.post('hideForm', [spanForm]);
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

      dispatcher.post('initForm', [spanForm, {
          alsoResize: '#span_types',
          width: 760,
          buttons: [{
              id: 'span_form_delete',
              text: "Delete",
              click: deleteSpan
            }, {
              id: 'span_form_reselect',
              text: 'Reselect',
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

      var spanFormSubmit = function(evt, typeRadio) {
        typeRadio = typeRadio || $('#span_form input:radio:checked');
        var type = typeRadio.val();
        dispatcher.post('hideForm', [spanForm]);
        $.extend(spanOptions, {
          action: 'createSpan',
          collection: coll,
          'document': doc,
          type: type,
          comment: $('#span_notes').val()
        });

        var attributes = {};
        $.each(attributeTypes, function(attrNo, attr) {
          var $input = $('#span_attr_' + Util.escapeQuotes(attr.type));
          if (attr.bool) {
            attributes[attr.type] = $input[0].checked;
          } else if ($input[0].selectedIndex) {
            attributes[attr.type] = $input.val();
          }
        });
        // unfocus all elements to prevent focus being kept after
        // hiding them
        spanForm.parent().find('*').blur();
        spanOptions.attributes = $.toJSON(attributes);
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
            dispatcher.post('hideForm', [importForm]);
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
        dispatcher.post('showForm', [importForm]);
        importForm.find('input, textarea').val('');
      });

      $('#undo_button').click(function() {
        if (coll && doc) {
          options = {
            'action': 'undo',
            'collection': coll,
            'document': doc
          }
          dispatcher.post('ajax', [options, 'edited']);
        }
      });


      var preventDefault = function(evt) {
        evt.preventDefault();
      }

      var waiter = $('#waiter');
      waiter.dialog({
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
      waiter.parent().css('opacity', '0');

      var isReloadOkay = function() {
        // do not reload while the user is in the middle of editing
        return arcDragOrigin == null && reselectedSpan == null;
      };

      var userReceived = function(_user) {
        that.user = _user;
      }

      var init = function() {
        dispatcher.post('annotationIsAvailable');
      };

      dispatcher.
          on('init', init).
          on('renderData', rememberData).
          on('collectionLoaded', rememberSpanSettings).
          on('spanAndAttributeTypesLoaded', spanAndAttributeTypesLoaded).
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
          on('mousemove', onMouseMove);
    };

    return AnnotatorUI;
})(jQuery, window);
