// -*- Mode: JavaScript; tab-width: 2; indent-tabs-mode: nil; -*-
// vim:set ft=javascript ts=2 sw=2 sts=2 cindent:
var AnnotatorUI = (function($, window, undefined) {
    var AnnotatorUI = function(dispatcher, svg) {
      var that = this;
      var arcDragOrigin = null;
      var arcDragOriginBox = null;
      var arcDragOriginGroup = null;
      var arcDragArc = null;
      var selectedRange = null;
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

      that.user = null;

      var svgElement = $(svg._svg);

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
            arcOptions['left'] = eventDesc.leftSpans.join(',');
            arcOptions['right'] = eventDesc.rightSpans.join(',');
          }
          $('#arc_origin').text(Visualizer.displayForm(originSpan.type) + ' ("' + data.text.substring(originSpan.from, originSpan.to) + '")');
          $('#arc_target').text(Visualizer.displayForm(targetSpan.type) + ' ("' + data.text.substring(targetSpan.from, targetSpan.to) + '")');
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
        var screenHeight = $(window).height() - 15; // TODO HACK - no idea why -15 is needed
        var screenWidth = $(window).width();
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
        if (el = $('#span_mod_Negation')[0]) {
          el.checked = span ? span.Negation : false;
        }
        if (el = $('#span_mod_Speculation')[0]) {
          el.checked = span ? span.Speculation : false;
        }
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
        dispatcher.post('ajax', [{
            action: 'possibleArcTypes',
            directory: dir,
            origin_type: originType,
            target_type: targetType,
          },
          function(jsonData) {
            if (jsonData.empty && !arcType) {
              // no valid choices
              dispatcher.post('messages',
                [[["No choices for " +
                   Visualizer.displayForm(originType) +
                   " -> " +
                   Visualizer.displayForm(targetType),
                   'warning']]]);
            } else {
              $('#arc_roles').html(jsonData.html);
              keymap = jsonData.keymap;
              if (arcId) {
                $('#arc_highlight_link').attr('href', document.location + '/' + arcId).show(); // TODO incorrect
                var el = $('#arc_' + arcType)[0];
                if (el) {
                  el.checked = true;
                }
              } else {
                $('#arc_highlight_link').hide();
                el = $('#arc_form input:radio:first')[0];
                if (el) {
                  el.checked = true;
                }
              }
              var confirmMode = $('#confirm_mode')[0].checked;
              if (!confirmMode) {
                arcForm.find('#arc_roles input:radio').click(arcFormSubmitRadio);
              }
              if (arcType) {
                $('#arc_form_delete').show();
                keymap[$.ui.keyCode.DELETE] = 'arc_form_delete';
              } else {
                $('#arc_form_delete').hide();
              }

              dispatcher.post('showForm', [arcForm]);
              $('#arc_form input:submit').focus();
              adjustToCursor(evt, arcForm.parent());
            }
          }]);
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
              $('#arc_origin').text(Visualizer.displayForm(originSpan.type)+' ("'+data.text.substring(originSpan.from, originSpan.to)+'")');
              $('#arc_target').text(Visualizer.displayForm(targetSpan.type)+' ("'+data.text.substring(targetSpan.from, targetSpan.to)+'")');
              fillArcTypesAndDisplayForm(evt, originSpan.type, targetSpan.type);
            }
          }
        } else if (!evt.ctrlKey) {
          // if not, then is it span selection? (ctrl key cancels)
          var sel = window.getSelection();
          if (sel.rangeCount) {
            selectedRange = sel.getRangeAt(0);
          }
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

            if (selectedFrom === selectedTo) {
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
            var spanText = data.text.substring(selectedFrom, selectedTo);
            if (spanText.indexOf("\n") != -1) {
              dispatcher.post('messages', [[['Error: cannot annotate across a sentence break', 'error']]]);
              reselectedSpan = null;
              svgElement.removeClass('reselect');
            } else {
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

      var rememberSpanSettings = function(response) {
        try {
          // XXX formatting
          //'<div class="span_wrapper"><fieldset><legend>Left</legend><div class="span_types">Foo</div></fieldset></div><div class="span_wrapper"><fieldset><legend>Right</legend><div class="span_types">Foo<br/>Foo<br/>Foo<br/>Foo<br/>Foo<br/>Foo<br/>Foo<br/>Foo<br/>Foo<br/>Foo<br/>Foo</div></fieldset></div>';
          $('#span_types').html(response.html).find('.type_scroller').addClass('ui-widget');
        } catch (x) {
          escaped = response.html.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
          dispatcher.post('messages', [[['Error: failed to display span form; received HTML:<br/>' + escaped, 'error']]]);
          $('#span_types').html('Error displaying form');
        }
        spanKeymap = response.keymap;
        // TODO: consider separating span and arc labels
        spanLabels = response.labels;
        arcLabels = response.labels;
        spanForm.find('#span_types input:radio').click(spanFormSubmitRadio);
        spanForm.find('.collapser').click(collapseHandler);
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

      // XXX delete later
      var splitSpanOnArgs = function(args) {
          $.extend(spanOptions, {
                  action: 'splitSpan',
                  // TODO XXX dunno how to get an array across, so catenating
                  'args': args.join('|'),
                  directory: dir,
                  'document': doc,
              });
          dispatcher.post('ajax', [spanOptions, 'edited']);
      }

      var splitSpanOnThemeSite = function() {
          splitSpanOnArgs(['Theme', 'Site']);
      }

      var splitSpanOnTheme = function() {
          splitSpanOnArgs(['Theme']);
      }

      var splitSpanOnSite = function() {
          splitSpanOnArgs(['Site']);
      }

      dispatcher.post('initForm', [spanForm, {
          // alsoResize: '#span_types', // DEBUG preparation for generated spans
          // XXX big hack :) choosing the exact thing to contract/expand
          alsoResize: '#span_types .type_scroller:last',
          width: 700,
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
        var el;
        var attributes = {};
        if (el = $('#span_mod_Negation')[0]) {
          attributes.negation = el.checked;
        }
        if (el = $('#span_mod_Speculation')[0]) {
          attributes.speculation = el.checked;
        }
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
          dispatcher.post('setDocument', [response.address]);
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
      });


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
      $('.login').hide();

      dispatcher.
        on('renderData', rememberData).
        on('dirLoaded', rememberSpanSettings).
        on('hideForm', hideForm).
        on('init', init).
        on('edited', edited).
        on('current', gotCurrent).
        on('keydown', onKeyDown).
        on('dblclick', onDblClick).
        on('mousedown', onMouseDown).
        on('mouseup', onMouseUp).
        on('mousemove', onMouseMove);
    };

    return AnnotatorUI;
})(jQuery, window);
