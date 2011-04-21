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

      that.user = null;

      var svgElement = $(svg._svg);

      var normalize = function(str) {
        return str.toLowerCase().replace(' ', '_');
      }

      var onKeyDown = function(evt) {
        if (!keymap) return;

        var key = evt.which;
        var binding = keymap[key];
        if (!binding) binding = keymap[String.fromCharCode(key)];
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
            action: 'arc',
            origin: originSpanId,
            target: targetSpanId,
            type: type,
            old: type,
            directory: dir,
            'document': doc
          };
          var eventDescId = target.attr('data-arc-ed');
          if (eventDescId) {
            var eventDesc = data.eventDescs[eventDescId];
            arcOptions['left'] = eventDesc.leftSpans.join(',');
            arcOptions['right'] = eventDesc.rightSpans.join(',');
          }
          $('#arc_origin').text(originSpan.type + ' ("' + data.text.substring(originSpan.from, originSpan.to) + '")');
          $('#arc_target').text(targetSpan.type + ' ("' + data.text.substring(targetSpan.from, targetSpan.to) + '")');
          var arcId = originSpanId + '--' + type + '--' + targetSpanId; // TODO
          fillArcTypesAndDisplayForm(evt, originSpan.type, targetSpan.type, type, arcId);
          
        // if not, then do we edit a span?
        } else if (id = target.attr('data-span-id')) {
          window.getSelection().removeAllRanges();
          var span = data.spans[id];
          spanOptions = {
            action: 'span',
            from: span.from,
            to: span.to,
            id: id,
          };
          var spanText = data.text.substring(span.from, span.to);
          fillSpanTypesAndDisplayForm(evt, spanText, span);
        }
      };

      var onMouseDown = function(evt) {
        if (!that.user || arcDragOrigin) return;
        var target = $(evt.target);
        var id;
        // is it arc drag start?
        if (id = target.attr('data-span-id')) {
          window.getSelection().removeAllRanges();
          svgPosition = svgElement.offset();
          arcDragOrigin = id;
          arcDragArc = svg.path(svg.createPath(), {
            markerEnd: 'url(#drag_arrow)',
            'class': 'drag_stroke',
            fill: 'none',
          });
          arcDragOriginGroup = $(data.spans[arcDragOrigin].group);
          arcDragOriginGroup.addClass('highlight');
          arcDragOriginBox = Brat.realBBox(data.spans[arcDragOrigin]);
          arcDragOriginBox.center = arcDragOriginBox.x + arcDragOriginBox.width / 2;
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
          $('#span_form_delete').show();
          keymap[$.ui.keyCode.DELETE] = 'span_form_delete';
          var el = $('#span_' + normalize(span.type));
          if (el.length) {
            el[0].checked = true;
          } else {
            $('#span_form input:radio:checked').each(function (radioNo, radio) {
              radio.checked = false;
            });
          }
        } else {
          $('#span_highlight_link').hide();
          $('#span_form_delete').hide();
          keymap[$.ui.keyCode.DELETE] = null;
          $('#span_form input:radio:first')[0].checked = true;
        }
        if (el = $('#span_mod_negation')[0]) {
          el.checked = span ? span.Negation : false;
        }
        if (el = $('#span_mod_speculation')[0]) {
          el.checked = span ? span.Speculation : false;
        }
        dispatcher.post('showForm', [spanForm]);
        $('#span_form-ok').focus();

        adjustToCursor(evt, spanForm.parent());
      };

      var arcFormSubmit = function(evt) {
        var type = $('#arc_form input:radio:checked').val();
        dispatcher.post('hideForm', [arcForm]);

        if (type) { // (if not cancelled)
          arcOptions.type = type;
          dispatcher.post('ajax', [arcOptions, 'edited']);
        } else {
          dispatcher.post('messages', [[['Error: No type selected', 'error']]]);
        }
        return false;
      };

      var fillArcTypesAndDisplayForm = function(evt, originType, targetType, arcType, arcId) {
        dispatcher.post('ajax', [{
            action: 'arctypes',
            directory: dir,
            origin: originType,
            target: targetType,
          }, 
          function(jsonData) {
            if (jsonData.empty && !arcType) {
              // no valid choices
              dispatcher.post('messages', [[["No choices for " + originType + " -> " + targetType, 'error']]]);
            } else {
              $('#arc_roles').html(jsonData.html);
              keymap = jsonData.keymap;
              if (arcId) {
                $('#arc_highlight_link').attr('href', document.location + '/' + arcId).show(); // TODO incorrect
                var el = $('#arc_' + normalize(arcType))[0];
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
                arcForm.find('#arc_roles input:radio').click(arcFormSubmit);
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
        arcOptions.action = 'unarc';
        dispatcher.post('ajax', [arcOptions, 'edited']);
      };

      var arcForm = $('#arc_form');
      dispatcher.post('initForm', [arcForm, {
          width: 500,
          buttons: [{
            id: 'arc_form_delete',
            text: "Delete",
            click: deleteArc
          }],
          close: function(evt) {
            keymap = null;
          }
        }]);
      arcForm.submit(arcFormSubmit);

      var onMouseUp = function(evt) {
        if (that.user === null) return;

        var target = $(evt.target);
        // is it arc drag end?
        if (arcDragOrigin) {
          arcDragOriginGroup.removeClass('highlight');
          target.parent().removeClass('highlight');
          if ((id = target.attr('data-span-id')) && arcDragOrigin != id) {
            var originSpan = data.spans[arcDragOrigin];
            var targetSpan = data.spans[id];
            arcOptions = {
              action: 'arc',
              origin: originSpan.id,
              target: targetSpan.id,
              directory: dir,
              'document': doc
            };
            $('#arc_origin').text(originSpan.type+' ("'+data.text.substring(originSpan.from, originSpan.to)+'")');
            $('#arc_target').text(targetSpan.type+' ("'+data.text.substring(targetSpan.from, targetSpan.to)+'")');
            fillArcTypesAndDisplayForm(evt, originSpan.type, targetSpan.type);
          }
          svg.remove(arcDragArc);
          arcDragOrigin = null;
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

            if (selectedFrom === selectedTo) return; // simple click (zero-width span)
            spanOptions = {
              action: 'span',
              from: selectedFrom,
              to: selectedTo
            };
            var spanText = data.text.substring(selectedFrom, selectedTo);
            if (spanText.indexOf("\n") != -1) {
              dispatcher.post('messages', [[['Error: cannot annotate across a sentence break', 'error']]]);
            } else {
              fillSpanTypesAndDisplayForm(evt, spanText);
            }
          }
        }
      };

      var init = function() {
        dispatcher.post('ajax', [{
            action: 'getuser'
          }, function(response) {
            var auth_button = $('#auth_button');
            if (response.user) {
              that.user = response.user;
              dispatcher.post('messages', [[['Welcome back, user "' + that.user + '"', 'info']]]);
              auth_button.val('Logout');
            } else {
              auth_button.val('Login');
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
        data = _data;
      };

      var rememberSpanSettings = function(response) {
        try {
          $('#span_types').html(response.html).find('.type_scroller').addClass('ui-widget');
        } catch (x) {
          escaped = response.html.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
          dispatcher.post('messages', [[['Error: failed to display span form; received HTML:<br/>' + escaped, 'error']]]);
          $('#span_types').html('Error displaying form');
        }
        spanKeymap = response.keymap;
        // TODO: consider separating span and arc abbreviations
        spanAbbrevs = response.abbrevs;
        arcAbbrevs = response.abbrevs;
        spanForm.find('#span_types input:radio').click(spanFormSubmitRadio);
        spanForm.find('.collapser').click(collapseHandler);
      };

      var gotCurrent = function(_dir, _doc, _args) {
        dir = _dir;
        doc = _doc;
        args = _args;
      };

      var edited = function(response) {
        args.edited = response.edited;
        data = response.annotations;
        data.document = doc;
        data.directory = dir;
        dispatcher.post('preventReloadByURL');
        dispatcher.post('setArguments', [args]);
        dispatcher.post('renderData', [data]);
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
            pass: password,
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
          }]);
        } else {
          dispatcher.post('showForm', [authForm]);
        }
      });
      authForm.submit(authFormSubmit);

      var spanForm = $('#span_form');

      var deleteSpan = function() {
        $.extend(spanOptions, {
          action: 'unspan',
          directory: dir,
          'document': doc,
        });
        dispatcher.post('ajax', [spanOptions, 'edited']);
        dispatcher.post('hideForm', [spanForm]);
        $('#waiter').dialog('open');
      };

      dispatcher.post('initForm', [spanForm, {
          width: 500,
          buttons: [{
            id: 'span_form_delete',
            text: "Delete",
            click: deleteSpan
          }],
          close: function(evt) {
            keymap = null;
          }
        }]);

      var spanFormSubmit = function(evt, typeRadio) {
        typeRadio = typeRadio || $('#span_form input:radio:checked');
        var type = typeRadio.val();
        dispatcher.post('hideForm', [spanForm]);
        if (type) {
          $.extend(spanOptions, {
            action: 'span',
            directory: dir,
            'document': doc,
            type: type
          });
          var el;
          if (el = $('#span_mod_negation')[0]) {
            spanOptions.negation = el.checked;
          }
          if (el = $('#span_mod_speculation')[0]) {
            spanOptions.speculation = el.checked;
          }
          $('#waiter').dialog('open');
          dispatcher.post('ajax', [spanOptions, 'edited']);
        } else {
          dispatcher.post('messages', [[['Error: No type selected', 'error']]]);
        }
        return false;
      };
      spanForm.submit(spanFormSubmit);

      var importForm = $('#import_form');
      var importFormSubmit = function(evt) {
        dispatcher.post('hideForm', [importForm]);
        var _docid = $('#import_docid').val();
        var _doctitle = $('#import_title').val();
        var _doctext = $('#import_text').val();
        var opts = {
          action : 'import',
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

      dispatcher.
        on('renderData', rememberData).
        on('dirLoaded', rememberSpanSettings).
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
