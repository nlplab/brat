// -*- Mode: JavaScript; tab-width: 2; indent-tabs-mode: nil; -*-
// vim:set ft=javascript ts=2 sw=2 sts=2 cindent:
var VisualizerUI = (function($, window, undefined) {
    var VisualizerUI = function(dispatcher, svg) {
      var that = this;

      var messagePostOutFadeDelay = 1000;
      var messageDefaultFadeDelay = 3000;
      var defaultFloatFormat = '%.1f/right';

      var documentListing = null; // always documents of current collection
      var selectorData = null;    // can be search results when available
      var searchActive = false;   // whether search results received and in use
      var loadedSearchData = null;

      var currentForm;

      var spanTypes = null;
      var relationTypesHash = null;
      // TODO: confirm unnecessary and remove
//       var attributeTypes = null;
      var data = null;
      var mtime = null;
      var searchConfig = null;
      var coll, doc, args;
      var pagingOffset = 0;
      var collScroll;
      var docScroll;
      var user = null;
      var annotationAvailable = false;

      var svgElement = $(svg._svg);
      var svgId = svgElement.parent().attr('id');

      var maxMessages = 100;

      var currentDocumentSVGsaved = false;
      var fileBrowserClosedWithSubmit = false;

      // normalization:
      var normServerDbByNormDbName = {};
      var normInfoCache = {};
      var normInfoCacheSize = 0;
      var normInfoCacheMaxSize = 100;

      var matchFocus = '';
      var matches = '';

      /* START "no svg" message - related */

      var noSvgTimer = null;

      // this is necessary for centering
      $('#no_svg_wrapper').css('display', 'table');
      // on initial load, hide the "no SVG" message
      $('#no_svg_wrapper').hide();

      var hideNoDocMessage = function() {
        clearTimeout(noSvgTimer);
        $('#no_svg_wrapper').hide(0);
        $('#source_files').show();
      }

      var showNoDocMessage = function() {
        clearTimeout(noSvgTimer);
        noSvgTimer = setTimeout(function() {
          $('#no_svg_wrapper').fadeIn(500);
        }, 2000);
        $('#source_files').hide();
      }
      
      /* END "no svg" message - related */

      /* START collection browser sorting - related */

      var lastGoodCollection = '/';
      var sortOrder = [2, 1]; // column (0..), sort order (1, -1)
      var collectionSortOrder; // holds previous sort while search is active
      var docSortFunction = function(a, b) {
          // parent at the top
          if (a[2] === '..') return -1;
          if (b[2] === '..') return 1;

          // then other collections
          var aIsColl = a[0] == "c";
          var bIsColl = b[0] == "c";
          if (aIsColl !== bIsColl) return aIsColl ? -1 : 1;

          // desired column in the desired order
          var col = sortOrder[0];
          var aa = a[col];
          var bb = b[col];
          if (selectorData.header[col - 2][1] === 'string-reverse') {
            aa = aa.split('').reverse().join('');
            bb = bb.split('').reverse().join('');
          }
          if (aa != bb) return (aa < bb) ? -sortOrder[1] : sortOrder[1];

          // prevent random shuffles on columns with duplicate values
          // (alphabetical order of documents)
          aa = a[2];
          bb = b[2];
          if (aa != bb) return (aa < bb) ? -1 : 1;
          return 0;
      };

      var makeSortChangeFunction = function(sort, th, thNo) {
          $(th).click(function() {
              // TODO: avoid magic numbers in access to the selector
              // data (column 0 is type, 1 is args, rest is data)
              if (sort[0] === thNo + 1) sort[1] = -sort[1];
              else {
                var type = selectorData.header[thNo - 1][1];
                var ascending = type === "string";
                sort[0] = thNo + 1;
                sort[1] = ascending ? 1 : -1;
              }
              selectorData.items.sort(docSortFunction);
              docScroll = 0;
              showFileBrowser(); // resort
          });
      }

      /* END collection browser sorting - related */


      /* START message display - related */

      var showPullupTrigger = function() {
        $('#pulluptrigger').show('puff');
      }

      var $messageContainer = $('#messages');
      var $messagepullup = $('#messagepullup');
      var pullupTimer = null;
      var displayMessages = function(msgs) {
        var initialMessageNum = $messagepullup.children().length;

        if (msgs === false) {
          $messageContainer.children().each(function(msgElNo, msgEl) {
              $(msgEl).remove();
          });
        } else {
          $.each(msgs, function(msgNo, msg) {
            var element;
            var timer = null;
            try {
              element = $('<div class="' + msg[1] + '">' + msg[0] + '</div>');
            }
            catch(x) {
              escaped = msg[0].replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
              element = $('<div class="error"><b>[ERROR: could not display the following message normally due to malformed XML:]</b><br/>' + escaped + '</div>');
            }
            var pullupElement = element.clone();
            $messageContainer.append(element);
            $messagepullup.append(pullupElement.css('display', 'none'));
            slideToggle(pullupElement, true, true);

            var fader = function() {
              if ($messagepullup.is(':visible')) {
                element.remove();
              } else {
                element.hide('slow', function() {
                  element.remove();
                });
              }
            };
            var delay = (msg[2] === undefined)
                          ? messageDefaultFadeDelay
                          : (msg[2] === -1)
                              ? null
                              : (msg[2] * 1000);
            if (delay === null) {
              var button = $('<input type="button" value="OK"/>');
              element.prepend(button);
              button.click(function(evt) {
                timer = setTimeout(fader, 0);
              });
            } else {
              timer = setTimeout(fader, delay);
              element.mouseover(function() {
                  clearTimeout(timer);
                  element.show();
              }).mouseout(function() {
                  timer = setTimeout(fader, messagePostOutFadeDelay);
              });
            }
            // setTimeout(fader, messageDefaultFadeDelay);
          });

          // limited history - delete oldest
          var $messages = $messagepullup.children();
          for (var i = 0; i < $messages.length - maxMessages; i++) {
            $($messages[i]).remove();
          }
        }

        // if there is change in the number of messages, may need to
        // tweak trigger visibility
        var messageNum = $messagepullup.children().length;
        if (messageNum != initialMessageNum) {
          if (messageNum == 0) {
            // all gone; nothing to trigger
            $('#pulluptrigger').hide('slow');
          } else if (initialMessageNum == 0) {
            // first messages, show trigger at fade
            setTimeout(showPullupTrigger, messageDefaultFadeDelay+250);
          }
        }
      };

      // hide pullup trigger by default, show on first message
      $('#pulluptrigger').hide();
      $('#pulluptrigger').
        mouseenter(function(evt) {
          $('#pulluptrigger').hide('puff');
          clearTimeout(pullupTimer);
          slideToggle($messagepullup.stop(), true, true, true);
        });
      $('#messagepullup').
        mouseleave(function(evt) {
          setTimeout(showPullupTrigger, 500);
          clearTimeout(pullupTimer);
          pullupTimer = setTimeout(function() {
            slideToggle($messagepullup.stop(), false, true, true);
          }, 500);
        });


      /* END message display - related */


      /* START comment popup - related */

      var cursor = { x: 0, y: 0 };
      var adjustToCursor = function(evt, element, offset, top, right) {
        if (evt) {
          cursor.x = evt.clientX;
          cursor.y = evt.clientY;
        }
        // get the real width, without wrapping
        element.css({ left: 0, top: 0 });
        var screenHeight = $(window).height();
        var screenWidth = $(window).width();
        // FIXME why the hell is this 22 necessary?!?
        var elementHeight = element.height() + 22;
        var elementWidth = element.width() + 22;
        var x, y;
        offset = offset || 0;
        if (top) {
          y = cursor.y - elementHeight - offset;
          if (y < 0) top = false;
        }
        if (!top) {
          y = cursor.y + offset;
        }
        if (right) {
          x = cursor.x + offset;
          if (x >= screenWidth - elementWidth) right = false;
        }
        if (!right) {
          x = cursor.x - elementWidth - offset;
        }
        if (y < 0) y = 0;
        if (x < 0) x = 0;
        element.css({ top: y, left: x });
      };

      var commentPopup = $('#commentpopup');
      var commentDisplayed = false;

      var displayCommentTimer = null;
      var displayComment = function(evt, target, comment, commentText, commentType, immediately) {
        var idtype;
        if (commentType) {
          // label comment by type, with special case for default note type
          var commentLabel;
          if (commentType == 'AnnotatorNotes') {
            commentLabel = '<b>Note:</b> ';
          } else {
            commentLabel = '<b>'+Util.escapeHTML(commentType)+':</b> ';
          }
          comment += commentLabel + Util.escapeHTMLwithNewlines(commentText);
          idtype = 'comment_' + commentType;
        }
        commentPopup[0].className = idtype;
        commentPopup.html(comment);
        adjustToCursor(evt, commentPopup, 10, true, true);
        clearTimeout(displayCommentTimer);
        /* slight "tooltip" delay to allow highlights to be seen
           before the popup obstructs them. */
        displayCommentTimer = setTimeout(function() {
          commentPopup.stop(true, true).fadeIn();
          commentDisplayed = true;
        }, immediately ? 0 : 500);
      };

      // to avoid clobbering on delayed response
      var commentPopupNormInfoSeqId = 0;

      var normInfoSortFunction = function(a, b) {
        // images at the top
        if (a[0].toLowerCase() == '<img>') return -1;
        if (b[0].toLowerCase() == '<img>') return 1;
        // otherwise stable
        return Util.cmp(a[2],b[2]);
      }

      var fillNormInfo = function(infoData, infoSeqId) {
        // extend comment popup with normalization data
        var norminfo = '';
        // flatten outer (name, attr, info) array (idx for sort)
        var infos = [];
        var idx = 0;
        for (var i = 0; i < infoData.length; i++) {
          for (var j = 0; j < infoData[i].length; j++) {
            var label = infoData[i][j][0];
            var value = infoData[i][j][1];
            infos.push([label, value, idx++]);
          }
        }
        // sort, prioritizing images (to get floats right)
        infos = infos.sort(normInfoSortFunction);
        // combine several consequtive values with the same label
        var combined = [];
        var prev_label = '';
        for (var i = 0; i < infos.length; i++) {
          var label = infos[i][0];
          var value = infos[i][1];
          if (label == prev_label) {
            combined[combined.length-1][1] += ', '+value;
          } else {
            combined.push([label, value]);
          }
          prev_label = label;
        }
        infos = combined;
        // generate HTML
        for (var i = 0; i < infos.length; i++) {
          var label = infos[i][0];
          var value = infos[i][1];
          if (label && value) {
            // special treatment for some label values
            if (label.toLowerCase() == '<img>') {
              norminfo += ('<img class="norm_info_img" src="'+
                           Util.escapeHTML(value)+
                           '"/>');
            } else {
              // normal, as text

              // max length restriction
              if (value.length > 300) {
                value = value.substr(0, 300) + ' ...';
              }

              norminfo += ('<span class="norm_info_label">'+
                           Util.escapeHTML(label)+
                           '</span>'+
                           '<span class="norm_info_value">'+':'+
                           Util.escapeHTML(value)+
                           '</span>'+
                           '<br/>');
            }
          }
        }
        var drop=$('#norm_info_drop_point_'+infoSeqId);
        if (drop.length) {
          drop.html(norminfo);
          adjustToCursor(null, commentPopup, 10, true, true);
        } else {
          console.log('norm info drop point not found!'); //TODO XXX
        }
      }

      var normCacheGet = function(dbName, dbKey, value) {
        return normInfoCache[dbName+':'+dbKey];
      }
      var normCachePut = function(dbName, dbKey, value) {
        // TODO: non-stupid cache max size limit
        if (normInfoCacheSize >= normInfoCacheMaxSize) {
          normInfoCache = {};
          normInfoCacheSize = 0;
        }
        normInfoCache[dbName+':'+dbKey] = value;
        normInfoCacheSize++;
      }

      var displaySpanComment = function(
          evt, target, spanId, spanType, mods, spanText, commentText, 
          commentType, normalizations) {

        var immediately = false;
        var comment = ( '<div><span class="comment_type_id_wrapper">' +
                        '<span class="comment_type">' +
                        Util.escapeHTML(Util.spanDisplayForm(spanTypes,
                                                             spanType)) +
                        '</span>' +
                        ' ' +
                        '<span class="comment_id">' +
                        'ID:'+Util.escapeHTML(spanId) +
                        '</span></span>' );
        if (mods.length) {
          comment += '<div>' + Util.escapeHTML(mods.join(', ')) + '</div>';
        }

        comment += '</div>';
        comment += ('<div class="comment_text">"' + 
                    Util.escapeHTML(spanText) + 
                    '"</div>');
        var validArcTypesForDrag = dispatcher.post('getValidArcTypesForDrag', [spanId, spanType]);
        if (validArcTypesForDrag && validArcTypesForDrag[0]) {
          if (validArcTypesForDrag[0].length) {
            comment += '<div>' + validArcTypesForDrag[0].join(', ') + '</div>';
          } else {
            $('rect[data-span-id="' + spanId + '"]').addClass('badTarget');
          }
          immediately = true;
        }
        // process normalizations
        var normsToQuery = [];
        $.each(normalizations, function(normNo, norm) {
          var dbName = norm[0], dbKey = norm[1];
          comment += ( '<hr/>' +
                       '<span class="comment_id">' +
                       Util.escapeHTML(dbName) + ':' +
                       Util.escapeHTML(dbKey) + '</span>');
          if (dbName in normServerDbByNormDbName &&
              normServerDbByNormDbName[dbName] != '<NONE>') {
            // DB available, add drop-off point to HTML and store
            // query parameters
            commentPopupNormInfoSeqId++;
            comment += ('<br/><div id="norm_info_drop_point_'+
                        commentPopupNormInfoSeqId+'"/>');
            normsToQuery.push([dbName, dbKey, commentPopupNormInfoSeqId]);
          } else {
            // no DB, just attach "human-readable" text provided
            // with the annotation, if any
            if (norm[2]) {
                comment += ('<br/><span class="norm_info_value">'+
                            Util.escapeHTML(norm[2])+'</span>');
            }
          }
        });

        // display initial comment HTML 
        displayComment(evt, target, comment, commentText, commentType, 
                       immediately);

        // initiate AJAX calls for the normalization data to query
        $.each(normsToQuery, function(normqNo, normq) {
          // TODO: cache some number of most recent norm_get_data results
          var dbName = normq[0], dbKey = normq[1], infoSeqId = normq[2];
          
          if (normCacheGet(dbName, dbKey)) {
            fillNormInfo(normCacheGet(dbName, dbKey), infoSeqId);
          } else {
            dispatcher.post('ajax', [{
              action: 'normData',
              database: dbName,
              key: dbKey,
              collection: coll,
            },
            function(response) {
              if (response.exception) {
                ; // TODO: response to error
              } else if (!response.value) {
                ; // TODO: response to missing key
              } else {
                fillNormInfo(response.value, infoSeqId);
                normCachePut(dbName, dbKey, response.value);
              }
            }]);
          }
        });
      };

      var onDocChanged = function() {
        commentPopup.hide();
        commentDisplayed = false;
      };

      var displayArcComment = function(
          evt, target, symmetric, arcId,
          originSpanId, originSpanType, role, 
          targetSpanId, targetSpanType,
          commentText, commentType) {
        var arcRole = target.attr('data-arc-role');
        // in arrowStr, &#8212 == mdash, &#8594 == Unicode right arrow
        var arrowStr = symmetric ? '&#8212;' : '&#8594;';
        var arcDisplayForm = Util.arcDisplayForm(spanTypes, 
                                                 data.spans[originSpanId].type, 
                                                 arcRole,
                                                 relationTypesHash);
        var comment = "";
        comment += ('<span class="comment_type_id_wrapper">' +
                    '<span class="comment_type">' +
                    Util.escapeHTML(Util.spanDisplayForm(spanTypes,
                                                         originSpanType)) +
                    ' ' + arrowStr + ' ' +
                    Util.escapeHTML(arcDisplayForm) +
                    ' ' + arrowStr + ' ' +
                    Util.escapeHTML(Util.spanDisplayForm(spanTypes,
                                                         targetSpanType)) +
                    '</span>' +
                    '<span class="comment_id">' +
                    (arcId ? 'ID:'+arcId : 
                     Util.escapeHTML(originSpanId) +
                     arrowStr + 
                     Util.escapeHTML(targetSpanId)) +
                    '</span>' +
                    '</span>');
        comment += ('<div class="comment_text">' + 
                    Util.escapeHTML('"'+data.spans[originSpanId].text+'"') +
                    arrowStr +
                    Util.escapeHTML('"'+data.spans[targetSpanId].text + '"') +
                    '</div>');
        displayComment(evt, target, comment, commentText, commentType);
      };

      var displaySentComment = function(
          evt, target, commentText, commentType) {
        displayComment(evt, target, '', commentText, commentType);
      };

      var hideComment = function() {
        clearTimeout(displayCommentTimer);
        if (commentDisplayed) {
          commentPopup.stop(true, true).fadeOut(function() { commentDisplayed = false; });
        }
      };

      var onMouseMove = function(evt) {
        if (commentDisplayed) {
          adjustToCursor(evt, commentPopup, 10, true, true);
        }
      };

      /* END comment popup - related */


      /* START form management - related */

      initForm = function(form, opts) {
        opts = opts || {};
        var formId = form.attr('id');

        // alsoResize is special
        var alsoResize = opts.alsoResize;
        delete opts.alsoResize;

        // Always add OK and Cancel
        var buttons = (opts.buttons || []);
        if (opts.no_ok) {
          delete opts.no_ok;
        } else {
          buttons.push({
              id: formId + "-ok",
              text: "OK",
              click: function() { form.submit(); }
            });
        }
        if (opts.no_cancel) {
          delete opts.no_cancel;
        } else {
          buttons.push({
              id: formId + "-cancel",
              text: "Cancel",
              click: function() { form.dialog('close'); }
            });
        }
        delete opts.buttons;

        opts = $.extend({
            autoOpen: false,
            closeOnEscape: true,
            buttons: buttons,
            modal: true
          }, opts);

        form.dialog(opts);
        form.on('dialogbeforeclose', function(evt) {
          if (form == currentForm) {
            currentForm = null;
          }
        });

        // HACK: jQuery UI's dialog does not support alsoResize
        // nor does resizable support a jQuery object of several
        // elements
        // See: http://bugs.jqueryui.com/ticket/4666
        if (alsoResize) {
          form.parent().resizable('option', 'alsoResize',
              '#' + form.attr('id') + ', ' + alsoResize);
        }
      };

      var unsafeDialogOpen = function($dialog) {
        // does not restrict tab key to the dialog
        // does not set the focus, nor change position
        // but is much faster than dialog('open') for large dialogs, see
        // https://github.com/nlplab/brat/issues/934

        var self = $dialog.dialog('instance');
        
        if (self._isOpen) { return; }

        self._isOpen = true;
        self.opener = $(self.document[0].activeElement);

        self._size();
        self._createOverlay();
        self._moveToTop(null, true);

        if (self.overlay) {
          self.overlay.css( "z-index", self.uiDialog.css( "z-index" ) - 1 );
        }
        self._show(self.uiDialog, self.options.show);
        self._trigger('open');
      };

      var showForm = function(form, unsafe) {
        currentForm = form;
        // as suggested in http://stackoverflow.com/questions/2657076/jquery-ui-dialog-fixed-positioning
        form.parent().css({position:"fixed"});
        if (unsafe) {
          unsafeDialogOpen(form);
        } else {
          form.dialog('open');
        }
        slideToggle($('#pulldown').stop(), false);
        return form;
      };

      var hideForm = function() {
        if (!currentForm) return;
        // currentForm.fadeOut(function() { currentForm = null; });
        currentForm.dialog('close');
      };

      /* END form management - related */


      /* START collection browser - related */

      var selectElementInTable = function(table, docname, mf) {
        table = $(table);
        table.find('tr').removeClass('selected');
        var sel = 'tr';
        var $element;
        if (docname) {
          sel += '[data-doc="' + docname + '"]';
          if (mf) {
            sel += '[data-mf="' + Util.paramArray(mf) + '"]';
          }
          var $element = table.find(sel).first();
          $element.addClass('selected');
        }
        matchFocus = $element && $element.attr('data-mf');
        matches = $element && $element.attr('data-match');
      }

      var chooseDocument = function(evt) {
        var $element = $(evt.target).closest('tr');
        $('#document_select tr').removeClass('selected');
        $('#document_input').val($element.attr('data-doc'));

        $element.addClass('selected');
        matchFocus = $element.attr('data-mf');
        matches = $element.attr('data-match');
      }

      var chooseDocumentAndSubmit = function(evt) {
        chooseDocument(evt);
        fileBrowserSubmit(evt);
      }

      var fileBrowser = $('#collection_browser');
      initForm(fileBrowser, {
          alsoResize: '#document_select',
          close: function(evt) {
            if (!doc) {
              // no document; set and show the relevant message, and
              // clear the "blind" unless waiting for a collection
              if (fileBrowserClosedWithSubmit) {
                $('#no_document_message').hide();
                $('#loading_message').show();
              } else {
                $('#loading_message').hide();
                $('#no_document_message').show();
                $('#waiter').dialog('close');
              }
              showNoDocMessage();
            } else if (!fileBrowserClosedWithSubmit && !searchActive) {
              dispatcher.post('setArguments', [{}, true]);
            }
          },
          width: 500
      });

      /* XXX removed per #900
      // insert the Save link
      var $fileBrowserButtonset = fileBrowser.
          parent().find('.ui-dialog-buttonpane .ui-dialog-buttonset').prepend(' ');
      $('<a href="ajax.cgi?action=downloadSearchFile" id="save_search">Save</a>').
          prependTo($fileBrowserButtonset).button().css('display', 'none');
      */

      var docInputHandler = function(evt) {
        selectElementInTable('#document_select', $(this).val());
      };
      $('#document_input').keyup(docInputHandler);

      var fileBrowserSubmit = function(evt) {
        var _coll, _doc, _args, found;
        var input = $('#document_input').
            val().
            replace(/\/?\s+$/, '').
            replace(/^\s+/, '');
        if (!input.length) return false;
        if (input.substr(0, 2) === '..') {
          // ..
          var pos = coll.substr(0, coll.length - 1).lastIndexOf('/');
          if (pos === -1) {
            dispatcher.post('messages', [[['At the root', 'error', 2]]]);
            $('#document_input').focus().select();
            return false;
          } else {
            _coll = coll.substr(0, pos + 1);
            _doc = '';
          }
        } else if (found = input.match(/^(\/?)((?:[^\/]*\/)*)([^\/?]*)$/)) {
          var abs = found[1];
          var collname = found[2].substr(0, found[2].length - 1);
          var docname = found[3];
          if (abs) {
            _coll = abs + collname;
            if (_coll.length < 2) coll += '/';
            _doc = docname;
          } else {
            if (collname) collname += '/';
            _coll = coll + collname;
            _doc = docname;
          }
        } else {
          dispatcher.post('messages', [[['Invalid document name format', 'error', 2]]]);
          $('#document_input').focus().select();
        }
        docScroll = $('#document_select')[0].scrollTop;
        fileBrowser.find('#document_select tbody').empty();

        if (coll != _coll || doc != _doc ||
            !Util.isEqual(Util.paramArray(args.matchfocus), (matchFocus || []))) {
          // something changed

          // set to allow keeping "blind" down during reload
          fileBrowserClosedWithSubmit = true;
          // ... and change BG message to a more appropriate one

          // trigger clear and changes if something other than the
          // current thing is chosen, but only blank screen before
          // render if the document changed (prevent "flicker" on
          // e.g. picking search results)
          if (coll != _coll || doc != _doc) {
            dispatcher.post('clearSVG');
          }
          dispatcher.post('allowReloadByURL');
          var newArgs = [];
          if (matchFocus) newArgs.push('matchfocus=' + matchFocus);
          if (matches) newArgs.push('match=' + matches);
          dispatcher.post('setCollection', [_coll, _doc, Util.deparam(newArgs.join('&'))]);
        } else {
          // hide even on select current thing
          hideForm();
        }
        return false;
      };
      fileBrowser.
          submit(fileBrowserSubmit).
          bind('reset', hideForm);

      var fileBrowserWaiting = false;
      var showFileBrowser = function() {
        // keep tabs on how the browser is closed; we need to keep the
        // "blind" up when retrieving a collection, but not when canceling
        // without selection (would hang the UI)
        fileBrowserClosedWithSubmit = false;

        // no point in showing this while the browser is shown
        hideNoDocMessage();

        if (currentForm == tutorialForm) {
          fileBrowserWaiting = true;
          return;
        }
        fileBrowserWaiting = false;

        // hide "no document" message when file browser shown
        // TODO: can't make this work; I can't detect when it gets hidden.
//         hideNoDocMessage();

        if (!(selectorData && showForm(fileBrowser))) return false;

        var html = ['<tr><th/>'];
        var tbody;
        $.each(selectorData.header, function(headNo, head) {
          html.push('<th>' + head[0] + '</th>');
        });
        html.push('</tr>');
        $('#document_select thead').html(html.join(''));

        html = [];
        // NOTE: we seem to have some excessive sorting going on;
        // disabling this as a test. If everything works, just remove
        // the following commented-out line (and this comment):
        //selectorData.items.sort(docSortFunction);
        $.each(selectorData.items, function(docNo, doc) {
          var isColl = doc[0] == "c"; // "collection"
          // second column is optional annotation-specific pointer,
          // used (at least) for search results
          var annp = doc[1] ? ('?' + Util.escapeHTML(Util.param(doc[1]))) : '';
          var name = Util.escapeHTML(doc[2]);
          var collFile = isColl ? 'collection' : 'file';
          //var collFileImg = isColl ? 'ic_list_folder.png' : 'ic_list_drafts.png';
          //var collFileImg = isColl ? 'Fugue-folder-horizontal-open.png' : 'Fugue-document.png';
          var collFileImg = isColl ? 'Fugue-shadowless-folder-horizontal-open.png' : 'Fugue-shadowless-document.png';
          var collSuffix = isColl ? '/' : '';
          if (doc[1]) {
            var matchfocus = doc[1].matchfocus || [];
            var mfstr = ' data-mf="' + Util.paramArray(matchfocus) + '"';
            var match = doc[1].match || [];
            var matchstr = ' data-match="' + Util.paramArray(match) + '"';
          } else {
            var matchstr = '';
            var mfstr = '';
          }
          html.push('<tr class="' + collFile + '" data-doc="'
            + name + collSuffix + '"' + matchstr + mfstr + '>');
          html.push('<th><img src="static/img/' + collFileImg + '" alt="' + collFile + '"/></th>');
          html.push('<th>' + name + collSuffix + '</th>');
          var len = selectorData.header.length - 1;
          for (var i = 0; i < len; i++) {
            var type = selectorData.header[i + 1][1];
            var datum = doc[i + 3];
            // format rest according to "data type" specified in header
            var formatted = null;
            var cssClass = null;
            if (!type) {
              console.error('Missing document list data type');
              formatted = datum;
            } else if (datum === undefined) {
              formatted = '';
            } else if (type === 'string') {
              formatted = Util.escapeHTML(datum);
            } else if (type === 'string-right' || type === 'string-reverse') {
              formatted = Util.escapeHTML(datum);
              cssClass = 'rightalign';
            } else if (type === 'string-center') {
              formatted = Util.escapeHTML(datum);
              cssClass = 'centeralign';
            } else if (type === 'time') {
              formatted = Util.formatTimeAgo(datum * 1000);
            } else if (type === 'float') {
              type = defaultFloatFormat;
              cssClass = 'rightalign';
            } else if (type === 'int') {
              formatted = '' + datum;
              cssClass = 'rightalign';
            }
            if (formatted === null) {
              var m = type.match(/^(.*?)(?:\/(right))?$/);
              cssClass = m[2] ? 'rightalign' : null;
              formatted = sprintf(m[1], datum);
            }
            html.push('<td' + (cssClass ? ' class="' + cssClass + '"' : '') + '>' +
                formatted + '</td>');
          }
          html.push('</tr>');
        });
        html = html.join('');
        tbody = $('#document_select tbody').html(html);
        $('#document_select')[0].scrollTop = docScroll;
        tbody.find('tr').
            click(chooseDocument).
            dblclick(chooseDocumentAndSubmit);

        $('#document_select thead tr *').each(function(thNo, th) {
            makeSortChangeFunction(sortOrder, th, thNo);
        });

        $('#collection_input').val(selectorData.collection);
        $('#document_input').val(doc);

        $('#readme').val(selectorData.description || '');
        if (selectorData.description && 
            (selectorData.description.match(/\n/) ||
             selectorData.description.length > 50)) {
          // multi-line or long description; show "more" button and fill
          // dialog text
          $('#more_readme_button').button(); // TODO: more reasonable place
          $('#more_readme_button').show();
          // only display text up to the first newline in the short info
          var split_readme_text = selectorData.description.match(/^[^\n]*/);
          $('#readme').val(split_readme_text[0]);
          $('#more_info_readme').text(selectorData.description);
        } else {
          // empty or short, single-line description; no need for more
          $('#more_readme_button').hide();
          $('#more_info_readme').text('');
        }

        selectElementInTable($('#document_select'), doc, args.matchfocus);
        setTimeout(function() {
          $('#document_input').focus().select();
        }, 0);
      }; // end showFileBrowser()
      $('#collection_browser_button').click(function(evt) {
        dispatcher.post('clearSearch');
      });

      var currentSelectorPosition = function() {
        var pos;
        $.each(selectorData.items, function(docNo, docRow) {
          if (docRow[2] == doc) {
            // args may have changed, so lacking a perfect match return
            // last matching document as best guess
            pos = docNo;
            // check whether 'focus' agrees; the rest of the args are
            // irrelevant for determining position.
            var collectionArgs = docRow[1] || {};
            if (Util.isEqual(collectionArgs.matchfocus, args.matchfocus)) {
              pos = docNo;
              return false;
            }
          }
        });
        return pos;
      }

      /* END collection browser - related */


      /* START search - related */

      var addSpanTypesToSelect = function($select, types, included) {
        if (!included) included = {};
        if (!included['']) {
          included[''] = true;
          $select.html('<option value="">- Any -</option>');
        }
        $.each(types, function(typeNo, type) {
          if (type !== null) {
            if (!included[type.name]) {
              included[type.name] = true;
              var $option = $('<option value="' + Util.escapeQuotes(type.type) + '"/>').text(type.name);
              $select.append($option);
              if (type.children) {
                addSpanTypesToSelect($select, type.children, included);
              }
            }
          }
        });
      };

      var rememberNormDb = function(response) {
        // the visualizer needs to remember aspects of the norm setup
        // so that it can avoid making queries for unconfigured or
        // missing normalization DBs.
        var norm_resources = response.normalization_config || [];
        $.each(norm_resources, function(normNo, norm) {
          var normName = norm[0];
          var serverDb = norm[3];
          normServerDbByNormDbName[normName] = serverDb;
        });
      }

      var setupSearchTypes = function(response) {
        addSpanTypesToSelect($('#search_form_entity_type'), response.entity_types);
        addSpanTypesToSelect($('#search_form_event_type'), response.event_types);
        addSpanTypesToSelect($('#search_form_relation_type'), response.relation_types);
        // nice-looking selects and upload fields
        $('#search_form select').addClass('ui-widget ui-state-default ui-button-text');
        $('#search_form_load_file').addClass('ui-widget ui-state-default ui-button-text');
      }

      // when event role changes, event types do as well
      var searchEventRoles = [];
      var searchEventRoleChanged = function(evt) {
        var $type = $(this).parent().next().children('select');
        var type = $type.val();
        var role = $(this).val();
        var origin = $('#search_form_event_type').val();
        var eventType = spanTypes[origin];
        var arcTypes = eventType && eventType.arcs || [];
        var arcType = null;
        $type.html('<option value="">- Any -</option>');
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
        if (type) {
          $type.val(type);
        };
      };

      $('#search_form_event_roles').on('change', '.search_event_role select', searchEventRoleChanged);

      // adding new role rows
      var addEmptySearchEventRole = function() {
        var $roles = $('#search_form_event_roles');
        var rowNo = $roles.children().length;
        var $role = $('<select class="fullwidth"/>');
        $role.append('<option value="">- Any -</option>');
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
        // style selector
        $role.addClass('ui-widget ui-state-default ui-button-text');
        $type.addClass('ui-widget ui-state-default ui-button-text');
        // style button
        button.button();
        button.addClass('small-buttons ui-button-text').removeClass('ui-button');
      };

      // deleting role rows
      var delSearchEventRole = function(evt) {
        $row = $(this).closest('tr');
        $row.remove();
      }

      $('#search_form_event_roles').on('click', '.search_event_role_add input', addEmptySearchEventRole);
      $('#search_form_event_roles').on('click', '.search_event_role_del input', delSearchEventRole);

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
        var $arg1 = $('#search_form_relation_arg1_type').
            html('<option value="">- Any -</option>');
        var $arg2 = $('#search_form_relation_arg2_type').empty();
        $.each(spanTypes,
          function(spanTypeType, spanType) {
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
        // style the selects
        $arg1.addClass('ui-widget ui-state-default ui-button-text');
        $arg2.addClass('ui-widget ui-state-default ui-button-text');
      });

      // when arg1 type changes, change choices of arg2 type
      $('#search_form_relation_arg1_type').change(function(evt) {
        var $arg2 = $('#search_form_relation_arg2_type').
            html('<option value="">- Any -</option>');
        var relType = $('#search_form_relation_type').val();
        var arg1Type = spanTypes[$(this).val()];
        var arcTypes = arg1Type && arg1Type.arcs || [];
        var arcType = null;
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

      $('#search_form_note_category').change(function(evt) {
        var category = $(this).val();
        var $type = $('#search_form_note_type');
        if ($.inArray(category, ['entity', 'event', 'relation']) != -1) {
          $type.html($('#search_form_' + category + '_type').html()).val('');
          $('#search_form_note_type_row:not(:visible)').show('highlight');
        } else {
          $type.html('');
          $('#search_form_note_type_row:visible').hide('highlight');
        }
      });


      // context length setting should only be visible if
      // concordancing is on
      // TODO: @amadanmath: help, my jQuery is horrible
      if ($('#concordancing_on').is(':checked')) {
        $('#context_size_div').show("highlight");
      } else {
        $('#context_size_div').hide("highlight");
      }
      $('#concordancing input[type="radio"]').change(function() {
        if ($('#concordancing_on').is(':checked')) {
          $('#context_size_div').show("highlight");
        } else {
          $('#context_size_div').hide("highlight");
        }
      });
      $('#search_options div.advancedOptions').hide("highlight");
      // set up advanced search options; only visible is clicked
      var advancedSearchOptionsVisible = false;
      $('#advanced_search_option_toggle').click(function(evt) {
        if (advancedSearchOptionsVisible) {
          $('#search_options div.advancedOptions').hide("highlight");
          $('#advanced_search_option_toggle').text("Show advanced");
        } else {
          $('#search_options div.advancedOptions').show("highlight");
          $('#advanced_search_option_toggle').text("Hide advanced");
        }
        advancedSearchOptionsVisible = !advancedSearchOptionsVisible;
        // block default
        return false;
      });

      var activeSearchTab = function() {
        // activeTab: 0 = Text, 1 = Entity, 2 = Event, 3 = Relation, 4 = Notes, 5 = Load
        var activeTab = $('#search_tabs').tabs('option', 'active');
        return ['searchText', 'searchEntity', 'searchEvent',
            'searchRelation', 'searchNote', 'searchLoad'][activeTab];
      }

      var onSearchTabSelect = function() {
        var action = activeSearchTab();
        switch (action) {
          case 'searchText':
            $('#search_form_text_text').focus().select();
            break;
          case 'searchEntity':
            $('#search_form_entity_text').focus().select();
            break;
          case 'searchEvent':
            $('#search_form_event_trigger').focus().select();
            break;
          case 'searchRelation':
            $('#search_form_relation_type').focus().select();
            break;
          case 'searchNote':
            $('#search_form_note_text').focus().select();
            break;
          case 'searchLoad':
            $('#search_form_load_file').focus().select();
            break;
        }
      };

      // set up jQuery UI elements in search form
      $('#search_tabs').tabs({
        show: onSearchTabSelect
      });
      $('#search_form').find('.radio_group').buttonset();

      var applySearchResults = function(response) {
        if (!searchActive) {
          collectionSortOrder = sortOrder;
        }
        dispatcher.post('searchResultsReceived', [response]);
        searchActive = true;
        updateSearchButtons();
      };

      var searchForm = $('#search_form');

      var searchFormSubmit = function(evt) {
        // hack around empty document; "" would be interpreted as
        // missing argument by server dispatcher (issue #513)
        // TODO: do this properly, avoiding magic strings
        var action = activeSearchTab();
        var docArg = doc ? doc : "/NO-DOCUMENT/";
        var opts = {
          action : action,
          collection : coll,
          document: docArg,
          // TODO the search form got complex :)
        };

        switch (action) {
          case 'searchText':
            opts.text = $('#search_form_text_text').val();
            if (!opts.text.length) {
              dispatcher.post('messages', [[['Please fill in the text to search for!', 'comment']]]);
              return false;
            }
            break;
          case 'searchEntity':
            opts.type = $('#search_form_entity_type').val() || '';
            opts.text = $('#search_form_entity_text').val();
            break;
          case 'searchEvent':
            opts.type = $('#search_form_event_type').val() || '';
            opts.trigger = $('#search_form_event_trigger').val();
            var eargs = [];
            $('#search_form_event_roles tr').each(function() {
              var earg = {};
              earg.role = $(this).find('.search_event_role select').val() || '';
              earg.type = $(this).find('.search_event_type select').val() || '';
              earg.text = $(this).find('.search_event_text input').val();
              eargs.push(earg);
            });
            opts.args = $.toJSON(eargs);
            break;
          case 'searchRelation':
            opts.type = $('#search_form_relation_type').val() || '';
            opts.arg1 = $('#search_form_relation_arg1_text').val();
            opts.arg1type = $('#search_form_relation_arg1_type').val() || '';
            opts.arg2 = $('#search_form_relation_arg2_text').val();
            opts.arg2type = $('#search_form_relation_arg2_type').val() || '';
            opts.show_text = $('#search_form_relation_show_arg_text_on').is(':checked');
            opts.show_type = $('#search_form_relation_show_arg_type_on').is(':checked');
            break;
          case 'searchNote':
            opts.category = $('#search_form_note_category').val() || '';
            opts.type = $('#search_form_note_type').val() || '';
            opts.text = $('#search_form_note_text').val() || '';
            break;
          case 'searchLoad':
            applySearchResults(loadedSearchData);
            return false;
        }

        // fill in scope of search ("document" / "collection")
        var searchScope = $('#search_scope input:checked').val();
        opts.scope = searchScope;

        // adjust specific action to invoke by scope
        if (searchScope == "document") {
          opts.action = opts.action + "InDocument";
        } else {
          opts.action = opts.action + "InCollection";
        }

        // fill in concordancing options
        opts.concordancing = $('#concordancing_on').is(':checked');
        opts.context_length = $('#context_length').val();

        // fill in text match options
        opts.text_match = $('#text_match input:checked').val()
        opts.match_case = $('#match_case_on').is(':checked');

        dispatcher.post('hideForm');
        dispatcher.post('ajax', [opts, function(response) {
          if(response && response.items && response.items.length == 0) {
            // TODO: might consider having this message come from the
            // server instead
            dispatcher.post('messages', [[['No matches to search.', 'comment']]]);
            dispatcher.post('clearSearch', [true]);
          } else {
            applySearchResults(response);
          }
        }]);
        return false;
      };

      $('#search_form_load_file').change(function(evt) {
        var $file = $('#search_form_load_file');
        var file = $file[0].files[0];
        var reader = new FileReader();
        reader.onerror = function(evt) {
          dispatcher.post('messages', [[['The file could not be read.', 'error']]]);
        };
        reader.onloadend = function(evt) {
          try {
            loadedSearchData = JSON.parse(evt.target.result);
            // TODO XXX check for validity of contents, not just whether
            // it's valid JSON or not; throw something if not
          } catch (x) {
            dispatcher.post('messages', [[['The file contains invalid data.', 'error']]]);
            return;
          }
        };
        reader.readAsText(file);
      });

      searchForm.submit(searchFormSubmit);

      initForm(searchForm, {
          width: 500,
          // alsoResize: '#search_tabs',
          resizable: false,
          open: function(evt) {
            keymap = {};
          },
      });
      $('#search_form_clear').attr('title', 'Clear the search and resume normal collection browsing');

      var showSearchForm = function() {
        // this.checked = searchActive; // TODO: dup? unnecessary? remove if yes.
        updateSearchButtons();
        $('#search_form_event_type').change();
        $('#search_form_relation_type').change();
        dispatcher.post('showForm', [searchForm]);
        onSearchTabSelect();
      }

      $('#search_button').click(showSearchForm);

      var clearSearchResults = function() {
        // clear UI, don't show collection browser
        dispatcher.post('clearSearch', [true]);
        // TODO: this was the only way I found to reset search. It
        // trigger an unnecessary round-trip to the server, though,
        // so there should be a better way ...
        dispatcher.post('setArguments', [{}, true]);
      }

      $('#clear_search_button').click(clearSearchResults);

      var updateSearchButtons = function() {
        $searchButton = $('#search_button');
        $searchButton[0].checked = searchActive;
        $searchButton.button('refresh');
        $clearSearchButton = $('#clear_search_button');
        if (searchActive) {
            // TODO: this is a bit poor form, using jQuery UI classes
            // directly -- are these names guaranteed to be stable?
            $('#search_button_label').removeClass('ui-corner-all');
            $('#search_button_label').addClass('ui-corner-left');
            $clearSearchButton.show();
        } else {
            $('#search_button_label').removeClass('ui-corner-left');
            $('#search_button_label').addClass('ui-corner-all');
            $clearSearchButton.hide();
        }
      }

      /* END search - related */


      /* START data dialog - related */

      var dataForm = $('#data_form');
      var dataFormSubmit = function(evt) {
        dispatcher.post('hideForm');
        return false;
      };
      dataForm.submit(dataFormSubmit);
      initForm(dataForm, {
          width: 500,
          resizable: false,
          no_cancel: true,
          open: function(evt) {
            keymap = {};
            // aspects of the data form relating to the current document should
            // only be shown when a document is selected.
            if (!doc) {
              $('#document_export').hide();
              $('#document_visualization').hide();
            } else {
              $('#document_export').show();
              $('#document_visualization').show();
              // the SVG button can only be accessed through the data form,
              // so we'll spare unnecessary saves by only saving here
              saveSVG();
            }
          }
      });
      $('#data_button').click(function() {
        dispatcher.post('showForm', [dataForm]);
      });
      // make nice-looking buttons for checkboxes and buttons
      $('#data_form').find('input[type="checkbox"]').button();
      $('#data_form').find('input[type="button"]').button();

      // resize invalidates stored visualization (SVG etc.); add a
      // button to regen
      $('#stored_file_regenerate').button().hide();
      $('#stored_file_regenerate').click(function(evt) {
        $('#stored_file_regenerate').hide();
        saveSVG();
      });

      /* END data dialog - related */


      /* START options dialog - related */

      var optionsForm = $('#options_form');
      var optionsFormSubmit = function(evt) {
        dispatcher.post('hideForm');
        return false;
      };
      optionsForm.submit(optionsFormSubmit);
      initForm(optionsForm, {
          width: 550,
          resizable: false,
          no_cancel: true,
          open: function(evt) {
            keymap = {};
          }
      });
      $('#options_button').click(function() {
        dispatcher.post('showForm', [optionsForm]);
      });
      // make nice-looking buttons for checkboxes and radios
      $('#options_form').find('input[type="checkbox"], input[type="button"]').button();
      $('#options_form').find('.radio_group').buttonset();
      $('#rapid_model').addClass('ui-widget ui-state-default ui-button-text');

      var fillDisambiguatorOptions = function(disambiguators) {
        $('#annotation_speed3').button(disambiguators.length ? 'enable': 'disable');
        //XXX: We need to disable rapid in the conf too if it is not available
        var $rapid_mode = $('#rapid_model').html('');
        $.each(disambiguators, function(modelNo, model) {
          var $option = $('<option/>').attr('value', model[2]).text(model[2]);
          $rapid_mode.append($option);
        });
      };

      /* END options dialog - related */


      /* START "more collection information" dialog - related */

      var moreInfoDialog = $('#more_information_dialog');
      var moreInfoDialogSubmit = function(evt) {
        dispatcher.post('hideForm');
        return false;
      };
      moreInfoDialog.submit(moreInfoDialogSubmit);
      initForm(moreInfoDialog, {
          width: 500,
          no_cancel: true,
          open: function(evt) {
            keymap = {};
          },
          alsoResize: '#more_info_readme',
      });
      $('#more_readme_button').click(function() {
        dispatcher.post('showForm', [moreInfoDialog]);
      });

      /* END "more collection information" dialog - related */


      var onKeyDown = function(evt) {
        var code = evt.which;

        if (code === $.ui.keyCode.ESCAPE) {
          dispatcher.post('messages', [false]);
          return;
        }

        if (currentForm) {
          if (code === $.ui.keyCode.ENTER) {
            // don't trigger submit in textareas to allow multiline text
            // entry
            // NOTE: spec seems to require this to be upper-case,
            // but at least chrome 8.0.552.215 returns lowercased
            var nodeType = evt.target.type ? evt.target.type.toLowerCase() : '';
            if (evt.target.nodeName && 
                evt.target.nodeName.toLowerCase() == 'input' && 
                (nodeType == 'text' || 
                 nodeType == 'password')) {
              currentForm.trigger('submit');
              return false;
            }
          } else if ((Util.isMac ? evt.metaKey : evt.ctrlKey) &&
                (code == 'F'.charCodeAt(0) || code == 'G'.charCodeAt(0))) {
            // prevent Ctrl-F/Ctrl-G in forms
            evt.preventDefault();
            return false;
          }
          return;
        }

        if (code === $.ui.keyCode.TAB) {
          showFileBrowser();
          return false;
        } else if (evt.shiftKey && code === $.ui.keyCode.RIGHT) {
          autoPaging(true);
        } else if (evt.shiftKey && code === $.ui.keyCode.LEFT) {
          autoPaging(false);
        } else if (evt.shiftKey && code === $.ui.keyCode.UP) {
          pagingOffset -= Configuration.pagingStep;
          if (pagingOffset < 0) pagingOffset = 0;
          dispatcher.post('setPagingOffset', [pagingOffset, true]);
        } else if (evt.shiftKey && code === $.ui.keyCode.DOWN) {
          pagingOffset += Configuration.pagingStep;
          dispatcher.post('setPagingOffset', [pagingOffset, true]);
        } else if (code == $.ui.keyCode.LEFT) {
          return moveInFileBrowser(-1);
        } else if (code === $.ui.keyCode.RIGHT) {
          return moveInFileBrowser(+1);
        } else if ((Util.isMac ? evt.metaKey : evt.ctrlKey) && code == 'F'.charCodeAt(0)) {
          evt.preventDefault();
          showSearchForm();
        } else if (searchActive && (Util.isMac ? evt.metaKey : evt.ctrlKey) && code == 'G'.charCodeAt(0)) {
          evt.preventDefault();
          return moveInFileBrowser(+1);
        } else if (searchActive && (Util.isMac ? evt.metaKey : evt.ctrlKey) && code == 'K'.charCodeAt(0)) {
          evt.preventDefault();
          clearSearchResults();
        }
      };

      var moveInFileBrowser = function(dir) {
        var pos = currentSelectorPosition();
        var newPos = pos + dir;
        if (newPos >= 0 && newPos < selectorData.items.length &&
            selectorData.items[newPos][0] != "c") {
          // not at the start, and the previous is not a collection (dir)
          dispatcher.post('allowReloadByURL');
          dispatcher.post('setDocument', [selectorData.items[newPos][2],
                                          selectorData.items[newPos][1]]);
        }
        return false;
      };
     
      /* Automatically proceed from document to document */ 
      var autoPagingTimeout = null;
      var autoPaging = function(on) {
          clearTimeout(autoPagingTimeout);
          if (on) {
            autoPagingTimeout = setInterval(function() {
              moveInFileBrowser(+1);
            }, 2000);
          }
      };

      var resizeFunction = function(evt) {
        dispatcher.post('renderData');
      };

      var resizerTimeout = null;
      var onResize = function(evt) {
        if (evt.target === window) {
          clearTimeout(resizerTimeout);
          resizerTimeout = setTimeout(resizeFunction, 100); // TODO is 100ms okay?
        }
      };

      var collectionLoaded = function(response) {
        if (response.exception) {
          if (response.exception == 'annotationCollectionNotFound' ||
              response.exception == 'collectionNotAccessible') {
              // revert to last good
              dispatcher.post('setCollection', [lastGoodCollection]);
          } else {
              dispatcher.post('messages', [[['Unknown error: ' + response.exception, 'error']]]);
              dispatcher.post('setCollection', ['/']);
          }
        } else {
          lastGoodCollection = response.collection;
          fillDisambiguatorOptions(response.disambiguator_config);
          selectorData = response;
          documentListing = response; // 'backup'
          searchConfig = response.search_config;
          selectorData.items.sort(docSortFunction);
          setupSearchTypes(response);
          // scroller at the top
          docScroll = 0;
        }
      };

      var searchResultsReceived = function(response) {
        if (response.exception) {
            ; // TODO: reasonable reaction
        } else {
          selectorData = response;
          sortOrder = [2, 1]; // reset
          // NOTE: don't sort, allowing order in which
          // responses are given to be used as default
          //selectorData.items.sort(docSortFunction);
          if (response.action.match(/Collection$/)) {
            showFileBrowser();
          } else {
            var item = response.items[0];
            dispatcher.post('setDocument', [item[2], item[1]]);
          }
          $('#save_search').css('display', 'inline-block');
        }
      };

      var clearSearch = function(dontShowFileBrowser) {
        dispatcher.post('hideForm');

        // back off to document collection
        if (searchActive) {
          $('#save_search').css('display', 'none');
          selectorData = documentListing;
          sortOrder = collectionSortOrder;
          selectorData.items.sort(docSortFunction);
          searchActive = false;
          updateSearchButtons();
        }

        if (!dontShowFileBrowser) {
          showFileBrowser();
        }
      }

      var saveSVGTimer = null;
      var saveSVG = function() {
        if (currentDocumentSVGsaved) {
          // no need to store again
          return false;
        }
        clearTimeout(saveSVGTimer);
        $('#stored_file_regenerate').hide();
        $('#stored_file_spinner').show()
        saveSVGTimer = dispatcher.post(1, 'ajax', [{
          action: 'storeSVG',
          svg: $('#svg').html(),
          collection: coll,
          document: doc
        }, 'savedSVG']);
      };

      var onDoneRendering = function(coll, doc, args) {
        if (args && !args.edited) {
          var svgtop = $('svg').offset().top;
          var $inFocus = $('#svg animate[data-type="focus"]:first').parent();
          if ($inFocus.length) {
            $('html,body').
                animate({ scrollTop: $inFocus.offset().top - svgtop - window.innerHeight / 2 }, { duration: 'slow', easing: 'swing'});
          }
        }
        dispatcher.post('allowReloadByURL');
        if (!currentForm) {
          $('#waiter').dialog('close');
        }
      }

      var onStartedRendering = function() {
        hideForm();
        if (!currentForm) {
          $('#waiter').dialog('open');
        }
      }

      var savedSVGreceived = function(response) {
        $('#stored_file_spinner').hide()

        if (response && response.exception == 'corruptSVG') {
          dispatcher.post('messages', [[['Cannot save SVG: corrupt', 'error']]]);
          return;
        }
        var $downloadStored = $('#download_stored').empty().show();
        $.each(response.stored, function(storedNo, stored) {
          var params = {
            'action': 'retrieveStored',
            'document': doc,
            'suffix': stored.suffix,
            // TODO: Extract the protocol version into somewhere global
            'protocol': 1
          };
          var $downloadLink = $('<a id="download_'+stored.name+'"' +
                                ' target="'+stored.name+'"' +
                                '>'+stored.name+'</a>');
          $downloadLink.attr('href', 'ajax.cgi?' + $.param(params));
          $downloadLink.button();
          if (storedNo) $downloadStored.append(' ');
          $downloadStored.append($downloadLink);
        });
        currentDocumentSVGsaved = true;
      };

      var invalidateSavedSVG = function() {
        // assuming that invalidation of the SVG invalidates all stored
        // static visualizations, as others are derived from the SVG
        $('#download_stored').hide();
        // have a way to regenerate if dialog open when data invalidated
        $('#stored_file_regenerate').show();
        currentDocumentSVGsaved = false;
      };

      var onNewSourceData = function(sourceData) {
        if (!sourceData) return;
        var $sourceFiles = $('#source_files').empty();
        /* Add download links for all available extensions */
        $.each(sourceData.source_files, function(extNo, ext) {
          var $link = $('<a target="brat_search"/>').
              text(ext).
              attr('href',
                  'ajax.cgi?action=downloadFile&collection=' + encodeURIComponent(coll) +
                  '&document=' + encodeURIComponent(doc) + '&extension=' + encodeURIComponent(ext) +
                  // TODO: Extract the protocol version into somewhere global
                  '&protocol=' + 1);
          $link.button();
          if (extNo) $sourceFiles.append(' ');
          $sourceFiles.append($link);
        });
        /* Add a download link for the whole collection */
        invalidateSavedSVG();

        mtime = sourceData.mtime;
        if (mtime) {
          // we're getting seconds and need milliseconds
          //$('#document_ctime').text("Created: " + Annotator.formatTime(1000 * sourceData.ctime)).css("display", "inline");
          $('#document_mtime').text("Last modified: " + Util.formatTimeAgo(1000 * mtime)).show();
        } else {
          //$('#document_ctime').css("display", "none");
          $('#document_mtime').hide();
        }
      }

      $('#source_collection_conf').buttonset();

      var gotCurrent = function(_coll, _doc, _args) {
        var oldColl = coll;

        coll = _coll;
        doc = _doc;
        args = _args;
        if (!args.edited) pagingOffset = 0;
        dispatcher.post('setPagingOffset', [pagingOffset]);

        // if we have a specific document, hide the "no document" message
        if (_doc) {
          hideNoDocMessage();
        }

        // if we have a collection change, update "collection download" and
        // "side-by-side comparison" buttons
        if (oldColl != coll) {
          var $sourceCollection = $('#source_collection').empty();
          var $collectionDownloadLink = $('<a target="brat_search"/>')
            .text('Download tar.gz')
            .attr('href', 'ajax.cgi?action=downloadCollection&collection=' + encodeURIComponent(coll)
            + '&include_conf=' + ($('#source_collection_conf_on').is(':checked') ? 1 : 0)
            // TODO: Extract the protocol version into somewhere global
            + '&protocol=' + 1);
          $sourceCollection.append($collectionDownloadLink);
          $collectionDownloadLink.button();

          $cmpButton = $('#side-by-side_cmp').empty();
          var $cmpLink = $('<a target="_blank"/>')
            .text('Comparison mode')
            .attr('href', 'diff.xhtml#?diff=' + encodeURIComponent(coll));
          $cmpButton.append($cmpLink);
          $cmpLink.button();
        }
          
        $docName = $('#document_name input').val(coll + doc);
        var docName = $docName[0];
        // TODO do this on resize, as well
        // scroll the document name to the right, so the name is visible
        // (even if the collection name isn't, fully)
        docName.scrollLeft = docName.scrollWidth;

        $('#document_mtime').hide();
        invalidateSavedSVG();
      };

      var slideToggle = function(el, show, autoHeight, bottom) {
        var el = $(el);
        var visible = el.is(":visible");
        var height;

        if (show === undefined) show = !visible;

        // @amadanmath: commenting this out appears to remove the annoying
        // misfeature where it's possible to stop the menu halfway by
        // mousing out and back in during closing. Please check that
        // this doesn't introduce other trouble and remove these lines.
//         if (show === visible) return false;

        if (!autoHeight) {
          height = el.data("cachedHeight");
        } else {
          el.height('auto');
        }
        if (!height) {
          height = el.show().height();
          el.data('cachedHeight', height);
          if (!visible) el.hide().css({ height: 0 });
        }

        if (show) {
          el.show().animate({ height: height }, {
            duration: 150,
            complete: function() {
              if (autoHeight) {
                el.height('auto');
              }
            },
            step: bottom ? function(now, fx) {
              fx.elem.scrollTop = fx.elem.scrollHeight;
            } : undefined
          });
        } else {
          el.animate({ height: 0 }, {
            duration: 300,
            complete: function() {
              el.hide();
            }
          });
        }
      }

      var menuTimer = null;
      $('#header').
        mouseenter(function(evt) {
          clearTimeout(menuTimer);
          slideToggle($('#pulldown').stop(), true);
        }).
        mouseleave(function(evt) {
          clearTimeout(menuTimer);
          menuTimer = setTimeout(function() {
            slideToggle($('#pulldown').stop(), false);
          }, 500);
        });

      $('#label_abbreviations input').click(function(evt) {
        var val = this.value;
        val = val === 'on';
        if (val) {
          dispatcher.post('messages', [[['Abbreviations are now on', 'comment']]]);
        } else {
          dispatcher.post('messages', [[['Abbreviations are now off', 'comment']]]);
        }
        dispatcher.post('abbrevs', [val]);
        // TODO: XXX: for some insane reason, doing the following call
        // synchronously breaks the checkbox (#456). If you ever figure
        // out why, it would make more sense to call
        //    dispatcher.post('resetData');
        // without the asynch.
        dispatcher.post(1, 'resetData');
      });

      $('#text_backgrounds input').click(function(evt) {
        var val = this.value;
        dispatcher.post('textBackgrounds', [val]);
        // TODO: XXX: see comment above for why this is asynchronous
        dispatcher.post(1, 'resetData');
      });

      $('#layout_density input').click(function(evt) {
        var val = this.value;
        dispatcher.post('layoutDensity', [val]);
        // TODO: XXX: see comment above for why this is asynchronous
        dispatcher.post(1, 'resetData');
        return false;
      });

      $('#svg_width_unit input').click(function(evt) {
        var width_unit = this.value;
        var width_value = $('#svg_width_value')[0].value;
        var val = width_value+width_unit;
        dispatcher.post('svgWidth', [val]);
        // TODO: XXX: see comment above for why this is asynchronous
        dispatcher.post(1, 'resetData');
        return false;
      });

      $('#annotation_speed input').click(function(evt) {
        var val = this.value;
        dispatcher.post('annotationSpeed', [val]);
        return false;
      });      
    
      $('#pulldown').find('input').button();
      var headerHeight = $('#mainHeader').height();
      $('#svg').css('margin-top', headerHeight + 10);
      aboutDialog = $('#about');
      aboutDialog.dialog({
            autoOpen: false,
            closeOnEscape: true,
            resizable: false,
            modal: true,
            open: function() {
              aboutDialog.find('*').blur();
            },
            beforeClose: function() {
              currentForm = null;
            }
          });
      $('#mainlogo').click(function() {
        showForm(aboutDialog);
      });

      // TODO: copy from annotator_ui; DRY it up
      var adjustFormToCursor = function(evt, element) {
        var screenHeight = $(window).height() - 8; // TODO HACK - no idea why -8 is needed
        var screenWidth = $(window).width() - 8;
        var elementHeight = element.height();
        var elementWidth = element.width();
        var y = Math.min(evt.clientY, screenHeight - elementHeight);
        var x = Math.min(evt.clientX, screenWidth - elementWidth);
        element.css({ top: y, left: x });
      };
      var viewspanForm = $('#viewspan_form');
      var onDblClick = function(evt) {
        if (user && annotationAvailable) return;
        var target = $(evt.target);
        var id;
        if (id = target.attr('data-span-id')) {
          window.getSelection().removeAllRanges();
          var span = data.spans[id];

          var urlHash = URLHash.parse(window.location.hash);
          urlHash.setArgument('focus', [[span.id]]);
          $('#viewspan_highlight_link').show().attr('href', urlHash.getHash());

          $('#viewspan_selected').text(span.text);
          var encodedText = encodeURIComponent(span.text);
          $.each(searchConfig, function(searchNo, search) {
            $('#viewspan_'+search[0]).attr('href', search[1].replace('%s', encodedText));
          });
          // annotator comments
          $('#viewspan_notes').val(span.annotatorNotes || '');
          dispatcher.post('showForm', [viewspanForm]);
          $('#viewspan_form-ok').focus();
          adjustFormToCursor(evt, viewspanForm.parent());
        }
      };
      viewspanForm.submit(function(evt) {
        dispatcher.post('hideForm');
        return false;
      });

      var authForm = $('#auth_form');
      initForm(authForm, { resizable: false });
      var authFormSubmit = function(evt) {
        dispatcher.post('hideForm');
        var _user = $('#auth_user').val();
        var password = $('#auth_pass').val();
        dispatcher.post('ajax', [{
            action: 'login',
            user: _user,
            password: password,
          },
          function(response) {
              if (response.exception) {
                dispatcher.post('showForm', [authForm]);
                $('#auth_user').select().focus();
              } else {
                user = _user;
                $('#auth_button').val('Logout ' + user);
                $('#auth_user').val('');
                $('#auth_pass').val('');
                $('.login').show();
                dispatcher.post('user', [user]);
              }
          }]);
        return false;
      };
      $('#auth_button').click(function(evt) {
        if (user) {
          dispatcher.post('ajax', [{
            action: 'logout'
          }, function(response) {
            user = null;
            $('#auth_button').val('Login');
            $('.login').hide();
            dispatcher.post('user', [null]);
          }]);
        } else {
          dispatcher.post('showForm', [authForm]);
        }
      });
      authForm.submit(authFormSubmit);


      var tutorialForm = $('#tutorial');
      var isWebkit = 'WebkitAppearance' in document.documentElement.style;
      if (!isWebkit) {
        // Inject the browser warning
        $('#browserwarning').css('display', 'block');
      }
      initForm(tutorialForm, {
        width: 800,
        height: 600,
        no_cancel: true,
        no_ok: true,
        buttons: [{
          id: "tutorial-ok",
          text: "OK",
          click: function() { tutorialForm.dialog('close'); }
        }],
        close: function() {
          if (fileBrowserWaiting) {
            showFileBrowser();
          }
        }
      });

      var init = function() {
        dispatcher.post('initForm', [viewspanForm, {
            width: 760,
            no_cancel: true
          }]);
        dispatcher.post('ajax', [{
            action: 'whoami'
          }, function(response) {
            var auth_button = $('#auth_button');
            if (response.user) {
              user = response.user;
              dispatcher.post('messages', [[['Welcome back, user "' + user + '"', 'comment']]]);
              auth_button.val('Logout ' + user);
              dispatcher.post('user', [user]);
              $('.login').show();
            } else if (response.anonymous) {
              user = 'Anonymous';
              auth_button.hide();
              dispatcher.post('user', [user]);
              $('.login').show();
            } else {
              user = null;
              auth_button.val('Login');
              dispatcher.post('user', [null]);
              $('.login').hide();
              // don't show tutorial if there's a specific document (annoyance)
              if (!doc) {
                dispatcher.post('showForm', [tutorialForm]);
                $('#tutorial-ok').focus();
              }
            }
          },
          { keep: true }
        ]);
        dispatcher.post('ajax', [{ action: 'loadConf' }, function(response) {
          if (response.config != undefined) {
            // TODO: check for exceptions
            try {
              Configuration = JSON.parse(response.config);
            } catch(x) {
              // XXX Bad config
              Configuration = {};
              dispatcher.post('messages', [[['Corrupted configuration; resetting.', 'error']]]);
              configurationChanged();
            }
            // TODO: make whole-object assignment work
            // @amadanmath: help! This code is horrible
            // Configuration.svgWidth = storedConf.svgWidth;
            dispatcher.post('svgWidth', [Configuration.svgWidth]);
            // Configuration.abbrevsOn = storedConf.abbrevsOn == "true";
            // Configuration.textBackgrounds = storedConf.textBackgrounds;
            // Configuration.rapidModeOn = storedConf.rapidModeOn == "true";
            // Configuration.confirmModeOn = storedConf.confirmModeOn == "true";
            // Configuration.autorefreshOn = storedConf.autorefreshOn == "true";
            if (Configuration.autorefreshOn) {
              checkForDocumentChanges();
            }
            // Configuration.visual.margin.x = parseInt(storedConf.visual.margin.x);
            // Configuration.visual.margin.y = parseInt(storedConf.visual.margin.y);
            // Configuration.visual.boxSpacing = parseInt(storedConf.visual.boxSpacing);
            // Configuration.visual.curlyHeight = parseInt(storedConf.visual.curlyHeight);
            // Configuration.visual.arcSpacing = parseInt(storedConf.visual.arcSpacing);
            // Configuration.visual.arcStartHeight = parseInt(storedConf.visual.arcStartHeight);
          }
          dispatcher.post('configurationUpdated');
        }]);
      };

      var noFileSpecified = function() {
        // not (only) an error, so no messaging
        dispatcher.post('clearSVG');
        showFileBrowser();
      }

      var showUnableToReadTextFile = function() {
        dispatcher.post('messages', [[['Unable to read the text file.', 'error']]]);
        dispatcher.post('clearSVG');
        showFileBrowser();
      };

      var showAnnotationFileNotFound = function() {
        dispatcher.post('messages', [[['Annotation file not found.', 'error']]]);
        dispatcher.post('clearSVG');
        showFileBrowser();
      };

      var showUnknownError = function(exception) {
        dispatcher.post('messages', [[['Unknown error: ' + exception, 'error']]]);
        dispatcher.post('clearSVG');
        showFileBrowser();
      };

      var reloadDirectoryWithSlash = function(sourceData) {
        var collection = sourceData.collection + sourceData.document + '/';
        dispatcher.post('setCollection', [collection, '', sourceData.arguments]);
      };

      // TODO: confirm attributeTypes unnecessary and remove
//       var spanAndAttributeTypesLoaded = function(_spanTypes, _attributeTypes) {
//         spanTypes = _spanTypes;
//         attributeTypes = _attributeTypes;
//       };
      // TODO: spanAndAttributeTypesLoaded is obviously not descriptive of
      // the full function. Rename reasonably.
      var spanAndAttributeTypesLoaded = function(_spanTypes, _entityAttributeTypes, _eventAttributeTypes, _relationTypesHash) {
        spanTypes = _spanTypes;
        relationTypesHash = _relationTypesHash;
      };

      var annotationIsAvailable = function() {
        annotationAvailable = true;
      };

      // hide anything requiring login, just in case
      $('.login').hide();

      // XXX TODO a lot
      var touchStart;
      var onTouchStart = function(evt) {
        // evt.preventDefault();
        evt = evt.originalEvent;
        if (evt.touches.length == 1) {
          // single touch; start tracking to see if we're doing
          // left/right
          touchStart = $.extend({}, evt.touches[0]); // clone
        } else if (evt.touches.length == 4) {
          // 4 finger tap: file browser
          showFileBrowser();
          return false;
        }
      };
      var onTouchEnd = function(evt) {
        // evt.preventDefault();
        evt = evt.originalEvent;
        $.each(evt.changedTouches, function(touchEndNo, touchEnd) {
          if (touchStart.identifier == touchEnd.identifier) {
            var dx = touchEnd.screenX - touchStart.screenX;
            var dy = touchEnd.screenY - touchStart.screenY;
            var adx = Math.abs(dx);
            var ady = Math.abs(dy);
            if (adx > 200 && ady < adx / 2) {
              // it's left/right!
              return moveInFileBrowser(dx < 0 ? -1 : +1);
            }
          }
        });
      };

      var documentChangesTimer = null;
      var maxDocumentChangesTimeout = 32 * 1000;
      var documentChangesTimeout = 1 * 1000;
      var checkForDocumentChanges = function() {
        if (coll && doc && dispatcher.post('isReloadOkay', [], 'all')) {
          opts = {
            'action': 'getDocumentTimestamp',
            'collection': coll,
            'document': doc
          }
          dispatcher.post('ajax', [opts, function(response) {
            if (data) {
              if (mtime != response.mtime) {
                dispatcher.post('current', [coll, doc, args, true]);
                documentChangesTimeout = 1 * 1000;
              } else {
                documentChangesTimeout *= 2;
                if (documentChangesTimeout >= maxDocumentChangesTimeout)
                  documentChangesTimeout = maxDocumentChangesTimeout;
              }
            }
          }]);
        } else {
          documentChangesTimeout = 1 * 1000;
        }
        documentChangesTimer = setTimeout(checkForDocumentChanges, documentChangesTimeout);
      }

      if (Configuration.autorefreshOn) {
        checkForDocumentChanges();
      }

      $('#autorefresh_mode').click(function(evt) {
        var val = this.checked;
        if (val) {
          Configuration.autorefreshOn = true;
          checkForDocumentChanges();
          dispatcher.post('messages', [[['Autorefresh mode is now on', 'comment']]]);
        } else {
          Configuration.autorefreshOn = false;
          clearTimeout(documentChangesTimer);
          dispatcher.post('messages', [[['Autorefresh mode is now off', 'comment']]]);
        }
        dispatcher.post('configurationChanged');
      });

      $('#type_collapse_limit').change(function(evt) {
        Configuration.typeCollapseLimit = parseInt($(this).val(), 10) || 0;
        dispatcher.post('configurationChanged');
      });

      $('#paging_size').change(function(evt) {
        Configuration.pagingSize = parseInt($(this).val(), 10) || 0;
        dispatcher.post('configurationChanged');
      });
      $('#paging_step').change(function(evt) {
        Configuration.pagingStep = parseInt($(this).val(), 10) || 0;
        dispatcher.post('configurationChanged');
      });
      $('#paging_clear').click(function(evt) {
        Configuration.pagingSize = 0;
        Configuration.pagingStep = 0;
        $('#paging_step, #paging_size').val('');
        dispatcher.post('configurationChanged');
      });

      var isReloadOkay = function() {
        // do not reload while the user is in the dialog
        return currentForm == null;
      };

      var configurationChanged = function() {
        // just assume that any config change makes stored
        // visualizations invalid. This is a bit excessive (not all
        // options affect visualization) but mostly harmless.
        invalidateSavedSVG();

        // save configuration changed by user action
        dispatcher.post('ajax', [{
                    action: 'saveConf',
                    config: JSON.stringify(Configuration),
                }, null]);
      };

      var updateConfigurationUI = function() {
        // update UI to reflect non-user config changes (e.g. load)
        
        // Annotation mode
        if (Configuration.confirmModeOn) {
          $('#annotation_speed1')[0].checked = true;
        } else if (Configuration.rapidModeOn) {
          $('#annotation_speed3')[0].checked = true;
        } else {
          $('#annotation_speed2')[0].checked = true;
        }
        $('#annotation_speed input').button('refresh');

        // Label abbrevs
        $('#label_abbreviations_on')[0].checked  = Configuration.abbrevsOn;
        $('#label_abbreviations_off')[0].checked = !Configuration.abbrevsOn; 
        $('#label_abbreviations input').button('refresh');

        // Text backgrounds        
        $('#text_backgrounds input[value="'+Configuration.textBackgrounds+'"]')[0].checked = true;
        $('#text_backgrounds input').button('refresh');

        // SVG width
        var splitSvgWidth = Configuration.svgWidth.match(/^(.*?)(px|\%)$/);
        if (!splitSvgWidth) {
          // TODO: reset to sensible value?
          dispatcher.post('messages', [[['Error parsing SVG width "'+Configuration.svgWidth+'"', 'error', 2]]]);
        } else {
          $('#svg_width_value')[0].value = splitSvgWidth[1];
          $('#svg_width_unit input[value="'+splitSvgWidth[2]+'"]')[0].checked = true;
          $('#svg_width_unit input').button('refresh');
        }

        // Autorefresh
        $('#autorefresh_mode')[0].checked = Configuration.autorefreshOn;
        $('#autorefresh_mode').button('refresh');

        // Type Collapse Limit
        $('#type_collapse_limit')[0].value = Configuration.typeCollapseLimit;

        // Paging
        $('#paging_size')[0].value = Configuration.pagingSize || '';
        $('#paging_step')[0].value = Configuration.pagingStep || '';
      }

      $('#prev').button().click(function() {
        return moveInFileBrowser(-1);
      });
      $('#next').button().click(function() {
        return moveInFileBrowser(+1);
      });
      $('#footer').show();

      $('#source_collection_conf_on, #source_collection_conf_off').change(function() {
        var conf = $('#source_collection_conf_on').is(':checked') ? 1 : 0;
        var $source_collection_link = $('#source_collection a');
        var link = $source_collection_link.attr('href').replace(/&include_conf=./, '&include_conf=' + conf);
        $source_collection_link.attr('href', link);
      });


      var rememberData = function(_data) {
        if (_data && !_data.exception) {
          data = _data;
        }
      };

      var onScreamingHalt = function() {
        $('#waiter').dialog('close');
        $('#pulldown, #navbuttons, #spinner').remove();
        dispatcher.post('hideForm');
      };

      dispatcher.
          on('init', init).
          on('dataReady', rememberData).
          on('annotationIsAvailable', annotationIsAvailable).
          on('messages', displayMessages).
          on('displaySpanComment', displaySpanComment).
          on('displayArcComment', displayArcComment).
          on('displaySentComment', displaySentComment).
          on('docChanged', onDocChanged).
          on('hideComment', hideComment).
          on('showForm', showForm).
          on('hideForm', hideForm).
          on('initForm', initForm).
          on('collectionLoaded', rememberNormDb).
          on('collectionLoaded', collectionLoaded).
          on('spanAndAttributeTypesLoaded', spanAndAttributeTypesLoaded).
          on('isReloadOkay', isReloadOkay).
          on('current', gotCurrent).
          on('doneRendering', onDoneRendering).
          on('startedRendering', onStartedRendering).
          on('newSourceData', onNewSourceData).
          on('savedSVG', savedSVGreceived).
          on('renderError:noFileSpecified', noFileSpecified).
          on('renderError:annotationFileNotFound', showAnnotationFileNotFound).
          on('renderError:unableToReadTextFile', showUnableToReadTextFile).
          on('renderError:isDirectoryError', reloadDirectoryWithSlash).
          on('unknownError', showUnknownError).
          on('keydown', onKeyDown).
          on('mousemove', onMouseMove).
          on('dblclick', onDblClick).
          on('touchstart', onTouchStart).
          on('touchend', onTouchEnd).
          on('resize', onResize).
          on('searchResultsReceived', searchResultsReceived).
          on('clearSearch', clearSearch).
          on('clearSVG', showNoDocMessage).
          on('screamingHalt', onScreamingHalt).
          on('configurationChanged', configurationChanged).
          on('configurationUpdated', updateConfigurationUI);
    };

    return VisualizerUI;
})(jQuery, window);
