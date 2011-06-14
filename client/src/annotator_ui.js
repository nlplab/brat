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
      var spanOptions = null;
      var arcOptions = null;
      var spanKeymap = null;
      var keymap = null;
      var dir = null;
      var doc = null;
      var reselectedSpan = null;
      var editedSpan = null;
      var repeatingArcTypes = [];
      var spanTypes = null;
      var attributeTypes = null;
      var searchActive = false;

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
          reselectedSpan = null;
          svgElement.removeClass('reselect');
          return;
        }

        if (!keymap) return;

        var binding = keymap[code];
        if (!binding) binding = keymap[String.fromCharCode(code)];
        if (binding) {
          $('#' + binding).click();
        }
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
            directory: dir,
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
          fillArcTypesAndDisplayForm(evt, originSpan.type, targetSpan.type, type, arcId);

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

      var fillSpanTypesAndDisplayForm = function(evt, spanText, span) {
        keymap = spanKeymap;
        if (span) {
          $('#del_span_button').show();
        } else {
          $('#del_span_button').hide();
        }
        $('#span_selected').text(spanText);
        var encodedText = encodeURIComponent(spanText);
        $('#span_uniprot').attr('href', 'http://www.uniprot.org/uniprot/?sort=score&query=' + encodedText);
        $('#span_entregene').attr('href', 'http://www.ncbi.nlm.nih.gov/gene?term=' + encodedText);
        $('#span_wikipedia').attr('href', 'http://en.wikipedia.org/wiki/Special:Search?search=' + encodedText);
        $('#span_google').attr('href', 'http://www.google.com/search?q=' + encodedText);
        $('#span_alc').attr('href', 'http://eow.alc.co.jp/' + encodedText);
        if (span) {
          // FIXME was: document.location + '/' + span.id);
          $('#span_highlight_link').show().attr('href', 'FIXME');
          var el = $('#span_' + span.type);
          if (el.length) {
            el[0].checked = true;
          } else {
            $('#span_form input:radio:checked').each(function (radioNo, radio) {
              radio.checked = false;
            });
          }
          // annotator comments
          if (span.annotatorNotes) {
            $('#span_notes').val(span.annotatorNotes);
          } else {
            $('#span_notes').val('');
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
          $('#span_form input:radio:first')[0].checked = true;
          $('#span_notes').val('');
          $('#span_form_split').hide();
        }
        if (span && !reselectedSpan) {
          $('#span_form_reselect, #span_form_delete').show();
          keymap[$.ui.keyCode.DELETE] = 'span_form_delete';
        } else {
          $('#span_form_reselect, #span_form_delete').hide();
          keymap[$.ui.keyCode.DELETE] = null;
        }
        $.each(attributeTypes, function(attrNo, attr) {
          $input = $('#span_attr_' + Util.escapeQuotes(attr.type));
          if (span) {
            if (attr.unused) {
              $input.val(span.attributes[attr.type] || '');
            } else if (attr.bool) {
              $input[0].checked = span.attributes[attr.type];
              $input.button('refresh');
            } else {
              $input.val(span.attributes[attr.type] || '').change();
            }
          }
        });
        dispatcher.post('showForm', [spanForm]);
        $('#span_form-ok').focus();

        adjustToCursor(evt, spanForm.parent());
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
        dispatcher.post('ajax', [arcOptions, 'edited']);
        return false;
      };

      var fillArcTypesAndDisplayForm = function(evt, originType, targetType, arcType, arcId) {
        var noArcs = true;
        keymap = {};

        if (spanTypes[originType]) {
          var arcTypes = spanTypes[originType].arcs;
          var $scroller = $('#arc_roles .scroller').empty();

          // lay them out into the form
          $.each(arcTypes, function(arcTypeNo, arcDesc) {
            if (arcDesc.targets && arcDesc.targets.indexOf(targetType) != -1) {
              var arcTypeName = arcDesc.type;
              var displayName = arcDesc.labels[0] || arcTypeName;
              if (arcDesc.hotkey) {
                keymap[arcDesc.hotkey] = '#arc_' + arcTypeName;
              }
              var $checkbox = $('<input id="arc_' + arcTypeName + '" type="radio" name="arc_type" value="' + arcTypeName + '"/>');
              var $label = $('<label for="arc_' + arcTypeName + '"/>').text(displayName);
              var $div = $('<div/>').append($checkbox).append($label);
              $scroller.append($div);

              noArcs = false;
            }
          });
        }

        if (noArcs) {
          if (arcId) {
            // let the user delete or whatever, even on bad config
            var $checkbox = $('<input id="arc_' + arcType + '" type="hidden" name="arc_type" value="' + arcType + '"/>');
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
          }

          $('#arc_form_delete').show();
          keymap[$.ui.keyCode.DELETE] = 'arc_form_delete';
        } else {
          // new arc
          $('#arc_highlight_link').hide();
          el = $('#arc_form input:radio:first')[0];
          if (el) {
            el.checked = true;
          }

          $('#arc_form_delete').hide();
        }

        var confirmMode = $('#confirm_mode')[0].checked;
        if (!confirmMode) {
          arcForm.find('#arc_roles input:radio').click(arcFormSubmitRadio);
        }

        dispatcher.post('showForm', [arcForm]);
        $('#arc_form input:submit').focus();
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
          svgElement.removeClass('reselect');
        }
      };

      var onMouseUp = function(evt) {
        if (that.user === null) return;

        var target = $(evt.target);
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
                directory: dir,
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
              reselectedSpan = null;
              svgElement.removeClass('reselect');
            } else {
              var spanText = data.text.substring(selectedFrom, selectedTo);
              fillSpanTypesAndDisplayForm(evt, spanText, reselectedSpan);
            }
          }
        }
      };

      var init = function() {
        dispatcher.post('ajax', [{
            action: 'whoami'
          }, function(response) {
            var auth_button = $('#auth_button');
            if (response.user) {
              that.user = response.user;
              dispatcher.post('messages', [[['Welcome back, user "' + that.user + '"', 'comment']]]);
              auth_button.val('Logout');
              $('.login').show();
            } else {
              auth_button.val('Login');
              $('.login').hide();
            }
          }
        ]);
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
          $('#span_form-ok').focus();
        } else {
          spanFormSubmit(evt, $(evt.target));
        }
      }

      var rememberData = function(_data) {
        if (_data) {
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
            var $label = $('<label/>').
              attr('for', 'span_' + type.type).
              text(name);
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
              name = name.replace(new RegExp("(&[^;]*?)?" + type.hotkey),
                function($0, $1) {
                  return $1 ? $0 : '<span class="accesskey">' + Util.escapeHTML(type.hotkey) + '</span>';
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

      // XXX If search form goes into visualizer_ui.js, this goes too
      var addSpanTypesToSelect = function($select, types) {
        $.each(types, function(typeNo, type) {
          if (type !== null) {
            var $option = $('<option value="' + Util.escapeQuotes(type.type) + '"/>').text(type.name);
            $select.append($option);
            if (type.children) {
              addSpanTypesToSelect($select, type.children);
            }
          }
        });
      };

      var rememberSpanSettings = function(response) {
        spanKeymap = {};

        $entities = $('<div id="entity_types" class="scroll_wrapper_half"/>');
        addSpanTypesToDiv($entities, response.entity_types, 'Entities');
        $events = $('<div id="event_types" class="scroll_wrapper_half"/>');
        addSpanTypesToDiv($events, response.event_types, 'Events');
        $('#span_types').empty().append($entities).append($events);

        var $attrs = $('#span_attributes div.scroller').empty();
        $.each(attributeTypes, function(attrNo, attr) {
          var escapedType = Util.escapeQuotes(attr.type);
          if (attr.unused) {
            var $input = $('<input type="hidden" id="span_attr_' + escapedType + '" value=""/>');
            $attrs.append($input);
          } else if (attr.bool) {
            var escapedName = Util.escapeQuotes(attr.name);
            var $input = $('<input type="checkbox" id="span_attr_' + escapedType + '" value="' + escapedType + '"/>');
            var $label = $('<label for="span_attr_' + escapedType + '">' + escapedName + '</label>');
            $attrs.append($input).append($label);
            $input.button();
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

        spanForm.find('#span_types input:radio').click(spanFormSubmitRadio);
        spanForm.find('.collapser').click(collapseHandler);

        // XXX If search form goes into visualizer_ui.js, this goes too
        addSpanTypesToSelect($('#search_form_entity_type'), response.entity_types);
        addSpanTypesToSelect($('#search_form_event_type'), response.event_types);
        addSpanTypesToSelect($('#search_form_relation_type'), response.relation_types);
      };

      var spanAndAttributeTypesLoaded = function(_spanTypes, _attributeTypes) {
        spanTypes = _spanTypes;
        attributeTypes = _attributeTypes;
      };

      var gotCurrent = function(_dir, _doc, _args) {
        dir = _dir;
        doc = _doc;
        args = _args;
      };

      var edited = function(response) {
        var x = response.exception;
        if (x) {
          if (x == 'annotationIsReadOnly') {
            dispatcher.post('messages', [[["This document is read-only and can't be edited.", 'error']]]);
          } else {
            dispatcher.message('unknownError', [x]);
          }
          reselectedSpan = null;
          svgElement.removeClass('reselect');
          $('#waiter').dialog('close');
        } else {
          args.edited = response.edited;
          data = response.annotations;
          data.document = doc;
          data.directory = dir;
          dispatcher.post('preventReloadByURL');
          dispatcher.post('setArguments', [args]);
          dispatcher.post('renderData', [data]);
        }
      };


      var authForm = $('#auth_form');
      dispatcher.post('initForm', [authForm]);
      var authFormSubmit = function(evt) {
        dispatcher.post('hideForm');
        var user = $('#auth_user').val();
        var password = $('#auth_pass').val();
        dispatcher.post('ajax', [{
            action: 'login',
            user: user,
            password: password,
          },
          function(response) {
              if (response.exception) {
                dispatcher.post('showForm', [authForm]);
                $('#auth_user').select().focus();
              } else {
                that.user = user;
                $('#auth_button').val('Logout');
                $('#auth_user').val('');
                $('#auth_pass').val('');
                $('.login').show();
              }
          }]);
        return false;
      };
      $('#auth_button').click(function(evt) {
        if (that.user) {
          dispatcher.post('ajax', [{
            action: 'logout'
          }, function(response) {
            that.user = null;
            $('#auth_button').val('Login');
            $('.login').hide();
          }]);
        } else {
          dispatcher.post('showForm', [authForm]);
        }
      });
      authForm.submit(authFormSubmit);

      var spanForm = $('#span_form');

      var deleteSpan = function() {
        var confirmMode = $('#confirm_mode')[0].checked;
        if (confirmMode && !confirm("Are you sure you want to delete this annotation?")) {
          return;
        }
        $.extend(spanOptions, {
          action: 'deleteSpan',
          directory: dir,
          'document': doc,
        });
        dispatcher.post('ajax', [spanOptions, 'edited']);
        dispatcher.post('hideForm', [spanForm]);
        $('#waiter').dialog('open');
      };

      var reselectSpan = function() {
        dispatcher.post('hideForm', [spanForm]);
        svgElement.addClass('reselect');
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
            directory: dir,
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
            reselectedSpan = null;
            svgElement.removeClass('reselect');
          }
        }]);

      var spanFormSubmit = function(evt, typeRadio) {
        typeRadio = typeRadio || $('#span_form input:radio:checked');
        var type = typeRadio.val();
        dispatcher.post('hideForm', [spanForm]);
        $.extend(spanOptions, {
          action: 'createSpan',
          directory: dir,
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
        dispatcher.post('hideForm', [importForm]);
        var _docid = $('#import_docid').val();
        var _doctitle = $('#import_title').val();
        var _doctext = $('#import_text').val();
        var opts = {
          action : 'importDocument',
          directory : dir,
          docid  : _docid,
          title : _doctitle,
          text  : _doctext,
        };
        dispatcher.post('ajax', [opts, function(response) {
          dispatcher.post('setDocument', [response.document]);
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
        importForm.find('input:text, textarea').val('');
      });


      // TODO: this should probably be in visualizer_ui instead

      // when event role changes, event types do as well
      var searchEventRoles = [];
      var searchEventRoleChanged = function(evt) {
        var $type = $(this).parent().next().children('select');
        var type = $type.val();
        $type.empty();
        var role = $(this).val();
        var origin = $('#search_form_event_type').val();
        var eventType = spanTypes[origin];
        var arcTypes = eventType && eventType.arcs || [];
        var arcType = null;
        $.each(arcTypes, function(arcNo, arcDesc) {
          if (arcDesc.type == role) {
            arcType = arcDesc;
            return false;
          }
        });
        var targets = arcType && arcType.targets || [];
        $.each(targets, function(targetNo, target) {
          var spanType = spanTypes[target];
          var spanName = spanType.name || spanType.labels[0] || target;
          var option = '<option value="' + Util.escapeQuotes(target) + '">' + Util.escapeHTML(spanName) + '</option>'
          $type.append(option);
        });
        // return the type to the same value, if possible
        $type.val(type);
      };
      $('#search_form_event_roles .search_event_role select').
        live('change', searchEventRoleChanged);
      // adding new role rows
      var addEmptySearchEventRole = function() {
        var $roles = $('#search_form_event_roles');
        var rowNo = $roles.children().length;
        var $role = $('<select class="fullwidth"/>');
        $.each(searchEventRoles, function(arcTypePairNo, arcTypePair) {
          var option = '<option value="' + Util.escapeQuotes(arcTypePair[0]) + '">' + Util.escapeHTML(arcTypePair[1]) + '</option>'
          $role.append(option);
        });
        var $type = $('<select class="fullwidth"/>');
        var $text = $('<input class="fullwidth"/>');
        var button = $('<input type="button"/>');
        var rowButton = $('<td/>').append(button);
        if (rowNo) {
          rowButton.addClass('search_event_role_del');
          button.val('\u2013'); // n-dash
        } else {
          rowButton.addClass('search_event_role_add');
          button.val('+');
        }
        var $tr = $('<tr/>').
          append($('<td class="search_event_role"/>').append($role)).
          append($('<td class="search_event_type"/>').append($type)).
          append($('<td class="search_event_text"/>').append($text)).
          append(rowButton);
        $roles.append($tr);
        $role.trigger('change');
      };
      // deleting role rows
      var delSearchEventRole = function(evt) {
        $row = $(this).closest('tr');
        $row.remove();
      }
      $('#search_form_event_roles .search_event_role_add input').
        live('click', addEmptySearchEventRole);
      $('#search_form_event_roles .search_event_role_del input').
        live('click', delSearchEventRole);

      // When event type changes, the event roles do as well
      // Also, put in one empty role row
      $('#search_form_event_type').change(function(evt) {
        var $roles = $('#search_form_event_roles').empty();
        searchEventRoles = [];
        var eventType = spanTypes[$(this).val()];
        var arcTypes = eventType && eventType.arcs || [];
        $.each(arcTypes, function(arcTypeNo, arcType) {
          var arcTypeName = arcType.labels && arcType.labels[0] || arcType.type;
          searchEventRoles.push([arcType.type, arcTypeName]);
        });
        addEmptySearchEventRole();
      });
      // when relation changes, change choices of arg1 type
      $('#search_form_relation_type').change(function(evt) {
        var relTypeType = $(this).val();
        var $arg1 = $('#search_form_relation_arg1_type').empty();
        var $arg2 = $('#search_form_relation_arg2_type').empty();
        $.each(spanTypes, function(spanTypeType, spanType) {
          if (spanType.arcs) {
            $.each(spanType.arcs, function(arcTypeNo, arcType) {
              if (arcType.type === relTypeType) {
                var spanName = spanType.name;
                var option = '<option value="' + Util.escapeQuotes(spanTypeType) + '">' + Util.escapeHTML(spanName) + '</option>'
                $arg1.append(option);
              }
            });
          }
        });
        $('#search_form_relation_arg1_type').change();
      });
      // when arg1 type changes, change choices of arg2 type
      $('#search_form_relation_arg1_type').change(function(evt) {
        var $arg2 = $('#search_form_relation_arg2_type').empty();
        var relType = $('#search_form_relation_type').val();
        var arg1Type = spanTypes[$(this).val()];
        var arcTypes = arg1Type && arg1Type.arcs;
        var arctype = null;
        $.each(arcTypes, function(arcNo, arcDesc) {
          if (arcDesc.type == relType) {
            arcType = arcDesc;
            return false;
          }
        });
        if (arcType && arcType.targets) {
          $.each(arcType.targets, function(spanTypeNo, spanTypeType) {
            var spanName = Util.spanDisplayForm(spanTypes, spanTypeType);
            var option = '<option value="' + Util.escapeQuotes(spanTypeType) + '">' + Util.escapeHTML(spanName) + '</option>'
            $arg2.append(option);
          });
        }
      });
      $('#search_tabs').tabs();
      var searchForm = $('#search_form');
      var searchFormSubmit = function(evt) {
        // activeTab: 0 = Text, 1 = Entity, 2 = Event, 3 = Relation
        var activeTab = $('#search_tabs').tabs('option', 'selected');
        dispatcher.post('hideForm', [searchForm]);
        var action = ['searchText', 'searchEntity', 'searchEvent', 'searchRelation'][activeTab];
        var opts = {
          action : action,
          directory : dir,
          // TODO the search form got complex :)
        };
        switch (action) {
          case 'searchText':
            opts.text = $('#search_form_text_text').val();
            break;
          case 'searchEntity':
            opts.type = $('#search_form_entity_type').val();
            opts.text = $('#search_form_entity_text').val();
            break;
          case 'searchEvent':
            opts.type = $('#search_form_event_type').val();
            opts.trigger = $('#search_form_event_trigger').val();
            var roles = [];
            $('#search_form_event_roles tr').each(function() {
              var role = {};
              role.role = $(this).find('.search_event_role select').val();
              role.type = $(this).find('.search_event_type select').val();
              role.text = $(this).find('.search_event_text input').val();
              roles.push(role);
            });
            opts.roles = $.toJSON(roles);
            break;
          case 'searchRelation':
            opts.type = $('#search_form_relation_type').val();
            opts.arg1 = $('#search_form_relation_arg1_type').val();
            opts.arg2 = $('#search_form_relation_arg2_type').val();
            break;
        }
        dispatcher.post('ajax', [opts, function(response) {
          dispatcher.post('searchResultsReceived', [response]); // TODO
          searchActive = true;
          updateSearchButton();
        }]);
        return false;
      };
      searchForm.submit(searchFormSubmit);
      dispatcher.post('initForm', [searchForm, {
          width: 500,
          alsoResize: '#search_tabs',
          open: function(evt) {
            keymap = {};
          },
          buttons: [{
            id: 'search_form_clear',
            text: "Clear",
            click: function(evt) {
              searchActive = false;
              updateSearchButton();
              // TODO get the directory again
              dispatcher.post('hideForm', [searchForm]);
            },
          }],
        }]);
      $('#search_button').click(function(evt) {
        this.checked = searchActive;
        updateSearchButton();
        $('#search_form_event_type').change();
        $('#search_form_relation_type').change();
        dispatcher.post('showForm', [searchForm]);
      });

      var updateSearchButton = function() {
        $searchButton = $('#search_button');
        $searchButton[0].checked = searchActive;
        $searchButton.button('refresh');
      }


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

      dispatcher.
        on('renderData', rememberData).
        on('dirLoaded', rememberSpanSettings).
        on('spanAndAttributeTypesLoaded', spanAndAttributeTypesLoaded).
        on('hideForm', hideForm).
        on('init', init).
        on('edited', edited).
        on('current', gotCurrent).
        on('keydown', onKeyDown).
        on('dblclick', onDblClick).
        on('dragstart', preventDefault).
        on('mousedown', onMouseDown).
        on('mouseup', onMouseUp).
        on('mousemove', onMouseMove);
    };

    return AnnotatorUI;
})(jQuery, window);
