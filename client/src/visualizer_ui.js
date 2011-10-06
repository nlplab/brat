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

      var currentForm;
      var spanTypes = null;
      var attributeTypes = null;
      var data = null;
      var coll, doc, args;
      var collScroll;
      var docScroll;
      var user = null;
      var annotationAvailable = false;

      var svgElement = $(svg._svg);
      var svgId = svgElement.parent().attr('id');


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
              if (sort[0] === thNo + 2) sort[1] = -sort[1];
              else {
                var type = selectorData.header[thNo][1];
                var ascending = type === "string";
                sort[0] = thNo + 2;
                sort[1] = ascending ? 1 : -1;
              }
              selectorData.items.sort(docSortFunction);
              showFileBrowser(); // resort
          });
      }

      /* END collection browser sorting - related */


      /* START message display - related */

      var messageContainer = $('#messages');
      var displayMessages = foo = function(msgs) {
        if (msgs === false) {
          messageContainer.children().each(function(msgElNo, msgEl) {
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
            messageContainer.append(element);
            var delay = (msg[2] === undefined)
                          ? messageDefaultFadeDelay
                          : (msg[2] === -1)
                              ? null
                              : (msg[2] * 1000);
            var fader = function() {
              element.hide('slow', function() {
                element.remove();
              });
            };
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
          });
        }
      };

      /* END message display - related */


      /* START comment popup - related */

      var adjustToCursor = function(evt, element, offset, top, right) {
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
          y = evt.clientY - elementHeight - offset;
          if (y < 0) top = false;
        }
        if (!top) {
          y = evt.clientY + offset;
        }
        if (right) {
          x = evt.clientX + offset;
          if (x >= screenWidth - elementWidth) right = false;
        }
        if (!right) {
          x = evt.clientX - elementWidth - offset;
        }
        if (y < 0) y = 0;
        if (x < 0) x = 0;
        element.css({ top: y, left: x });
      };

      var commentPopup = $('#commentpopup');
      var commentDisplayed = false;

      var displayComment = function(evt, target, comment, commentText, commentType) {
        var idtype;
        if (commentType) {
          comment += Util.escapeHTMLwithNewlines(commentText);
          idtype = 'comment_' + commentType;
        }
        commentPopup[0].className = idtype;
        commentPopup.html(comment);
        adjustToCursor(evt, commentPopup, 10, true, true);
        commentPopup.stop(true, true).fadeIn();
        commentDisplayed = true;
      };

      var displaySpanComment = function(
          evt, target, spanId, spanType, mods, spanText, commentText, commentType) {

          var comment = '<div><span class="comment_id">' + Util.escapeHTML(spanId) + '</span>' +
            ' ' + '<span class="comment_type">' + Util.escapeHTML(Util.spanDisplayForm(spanTypes, spanType)) + '</span>';
        if (mods.length) {
          comment += '<div>' + Util.escapeHTML(mods.join(', ')) + '</div>';
        }
        comment += '</div>';
        comment += '<div>"' + Util.escapeHTML(spanText) + '"</div>';
        displayComment(evt, target, comment, commentText, commentType);
      };

      var displayArcComment = function(
          evt, target, symmetric, arcId,
          originSpanId, role, targetSpanId, commentText, commentType) {
        var arcRole = target.attr('data-arc-role');
        var arrowStr = symmetric ? ' &#8212; ' : ' &#8594; '; // &#8212 == mdash, &#8594 == Unicode right arrow
        var comment = ( '<div class="comment_id">' +
                        (arcId ? arcId+': ' : '') +
                        Util.escapeHTML(originSpanId) +
                        arrowStr + 
                        Util.escapeHTML(Util.arcDisplayForm(spanTypes, data.spans[originSpanId].type, arcRole)) +
                        arrowStr + 
                        Util.escapeHTML(targetSpanId) +
                        '</div>' );
        comment += ('<div>' + Util.escapeHTML('"'+data.spans[originSpanId].text+'"') +
                    arrowStr +
                    Util.escapeHTML('"'+data.spans[targetSpanId].text + '"') + '</div>');
        displayComment(evt, target, comment, commentText, commentType);
      };

      var displaySentComment = function(
          evt, target, commentText, commentType) {
        displayComment(evt, target, '', commentText, commentType);
      };

      var hideComment = function() {
        commentPopup.stop(true, true).fadeOut(function() { commentDisplayed = false; });
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
        form.bind('dialogclose', function() {
            currentForm = null;
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

      var showForm = function(form) {
        currentForm = form;
        // as suggested in http://stackoverflow.com/questions/2657076/jquery-ui-dialog-fixed-positioning
        form.parent().css({position:"fixed"});
        form.dialog('open');
        slideToggle($('#pulldown').stop(), false);
        return form;
      };

      var hideForm = function(form) {
        if (form === undefined) form = currentForm;
        if (!form) return;
        // fadeOut version:
        // form.fadeOut(function() { currentForm = null; });
        form.dialog('close');
        if (form === currentForm) currentForm = null;
      };

      /* END form management - related */


      /* START collection browser - related */

      var selectElementInTable = function(table, value) {
        table = $(table);
        table.find('tr').removeClass('selected');
        if (value) {
          table.find('tr[data-value="' + value + '"]').addClass('selected');
        }
      }

      var chooseDocument = function(evt) {
        var docname = $(evt.target).closest('tr').attr('data-value');
        $('#document_input').val(docname);
        selectElementInTable('#document_select', docname);
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
              $('#waiter').dialog('close');
            }
          },
          width: 500
      });
      $('#document_input').change(function(evt) {
        selectElementInTable('#document_select', $(this).val());
      });

      var fileBrowserSubmit = function(evt) {
        var _coll, _doc, _args, found;
        var input = $('#document_input').
            val().
            replace(/\/?\s+$/, '').
            replace(/^\s+/, '');
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
        } else if (found = input.match(/^(\/?)((?:[^\/]*\/)*)([^\/?]*)(?:\?(.*))?$/)) {
          var abs = found[1];
          var collname = found[2].substr(0, found[2].length - 1);
          var docname = found[3];
          var args = found[4];
          if (abs) {
            _coll = abs + collname;
            if (_coll.length < 2) coll += '/';
            _doc = docname;
          } else {
            if (collname) collname += '/';
            _coll = coll + collname;
            _doc = docname;
          }
          if (args) {
              _args = Util.deparam(args);
          } else {
              _args = {};
          }
        } else {
          dispatcher.post('messages', [[['Invalid document name format', 'error', 2]]]);
          $('#document_input').focus().select();
        }
        docScroll = $('#document_select')[0].scrollTop;
        fileBrowser.find('#document_select tbody').empty();
        dispatcher.post('allowReloadByURL');
        dispatcher.post('setCollection', [_coll, _doc, _args]);
        return false;
      };
      fileBrowser.
          submit(fileBrowserSubmit).
          bind('reset', hideForm);

      var showFileBrowser = function() {
        if (!(selectorData && showForm(fileBrowser))) return false;

        var html = ['<tr>'];
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
          var annp = doc[1] ? ('?' + Util.param(doc[1])) : '';
          var name = doc[2];
          var collFile = isColl ? 'dir' : 'file';
          var collSuffix = isColl ? '/' : '';
          html.push('<tr class="' + collFile + '" data-value="'
                    + name + collSuffix + annp + '"><th>'
                    + name + collSuffix + '</th>');
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
              formatted = datum;
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
              formatted = $.sprintf(m[1], datum);
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
        var curcoll = selectorData.collection;
        var pos = curcoll.lastIndexOf('/');
        if (pos != -1) curcoll = curcoll.substring(pos + 1);
        selectElementInTable($('#collection_select'), curcoll);
        selectElementInTable($('#document_select'), doc);
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
            if (Util.isEqual(collectionArgs.focus, args.focus)) {
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

      var setupSearchTypes = function(response) {
        addSpanTypesToSelect($('#search_form_entity_type'), response.entity_types);
        addSpanTypesToSelect($('#search_form_event_type'), response.event_types);
        addSpanTypesToSelect($('#search_form_relation_type'), response.relation_types);
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
        } else if ($type.children().length == 2) {
          $type[0].selectedIndex = 1;
        };
      };

      $('#search_form_event_roles .search_event_role select').live('change', searchEventRoleChanged);

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
        if ($role.children().length == 2) {
          $role[0].selectedIndex = 1;
        };
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

      $('#search_form_event_roles .search_event_role_add input').live('click', addEmptySearchEventRole);
      $('#search_form_event_roles .search_event_role_del input').live('click', delSearchEventRole);

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
        if ($arg1.children().length == 2) {
          $arg1[0].selectedIndex = 1;
        };
        $('#search_form_relation_arg1_type').change();
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
        if ($arg2.children().length == 2) {
          $arg2[0].selectedIndex = 1;
        };
      });

      $('#search_tabs').tabs();

      var searchForm = $('#search_form');

      var searchFormSubmit = function(evt) {
        // activeTab: 0 = Text, 1 = Entity, 2 = Event, 3 = Relation
        var activeTab = $('#search_tabs').tabs('option', 'selected');
        var action = ['searchText', 'searchEntity', 'searchEvent', 'searchRelation'][activeTab];
        var opts = {
          action : action,
          collection : coll,
          // TODO the search form got complex :)
        };
        switch (action) {
          case 'searchText':
            opts.text = $('#search_form_text_text').val();
            if (!opts.text.length) {
              dispatcher.post('messages', [[['Text search query cannot be empty', 'error']]]);
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
            break;
        }
        dispatcher.post('hideForm', [searchForm]);
        dispatcher.post('ajax', [opts, function(response) {
          if(response && response.items && response.items.length == 0) {
            // TODO: might consider having this message come from the
            // server instead
            dispatcher.post('messages', [[['No matches to search.', 'comment']]]);
          } else {
            if (!searchActive) {
              collectionSortOrder = sortOrder;
            }
            dispatcher.post('searchResultsReceived', [response]);
            searchActive = true;
            updateSearchButton();
          }
        }]);
        return false;
      };

      searchForm.submit(searchFormSubmit);

      initForm(searchForm, {
          width: 500,
          alsoResize: '#search_tabs',
          open: function(evt) {
            keymap = {};
          },
          buttons: [{
            id: 'search_form_clear',
            text: "Clear",
            click: function(evt) {
              dispatcher.post('clearSearch');
            },
          }],
      });

      $('#search_button').click(function(evt) {
        // this.checked = searchActive; // TODO: dup? unnecessary? remove if yes.
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

      /* END search - related */

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
            var nodeType = evt.target.type.toLowerCase();
            if (evt.target.nodeName.toLowerCase() == 'input' && (nodeType == 'text' || nodeType == 'password')) {
              currentForm.trigger('submit');
              return false;
            }
          }
          return;
        }

        if (code === $.ui.keyCode.TAB) {
          showFileBrowser();
          return false;
        } else if (code == $.ui.keyCode.LEFT) {
          var pos = currentSelectorPosition();
          if (pos > 0 && selectorData.items[pos - 1][0] != "c") {
            // not at the start, and the previous is not a collection (dir)
            var newPos = pos - 1;
            dispatcher.post('allowReloadByURL');
            dispatcher.post('setDocument', [selectorData.items[newPos][2],
                                            selectorData.items[newPos][1]]);
          }
          return false;
        } else if (code === $.ui.keyCode.RIGHT) {
          var pos = currentSelectorPosition();
          if (pos < selectorData.items.length - 1) {
            // not at the end
            var newPos = pos + 1;
            dispatcher.post('allowReloadByURL');
            dispatcher.post('setDocument', [selectorData.items[newPos][2],
                                            selectorData.items[newPos][1]]);
          }
          return false;
        }
      };

      var resizeFunction = function(evt) {
        dispatcher.post('renderData');
      };

      var resizerTimeout = null;
      var onResize = function(evt) {
        clearTimeout(resizerTimeout);
        resizerTimeout = setTimeout(resizeFunction, 100); // TODO is 100ms okay?
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
          selectorData = response;
          documentListing = response; // 'backup'
          selectorData.items.sort(docSortFunction);
          setupSearchTypes(response);
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
          showFileBrowser();
        }
      };

      var clearSearch = function() {
        dispatcher.post('hideForm', [searchForm]);

        // back off to document collection
        if (searchActive) {
          selectorData = documentListing;
          sortOrder = collectionSortOrder;
          selectorData.items.sort(docSortFunction);
          searchActive = false;
          updateSearchButton();
        }

        showFileBrowser();
      }

      var saveSVGTimer = null;
      var saveSVG = function() {
        clearTimeout(saveSVGTimer);
        saveSVGTimer = dispatcher.post(500, 'ajax', [{
          action: 'storeSVG',
          svg: $('#svg').html()
        }, 'savedSVG']);
      };

      var onDoneRendering = function(coll, doc, args) {
        if (!args.edited) {
          var svgtop = $('svg').offset().top;
          var $inFocus = $('#svg animate[data-type="focus"]:first').parent();
          if ($inFocus.length) {
            $('html,body').
                animate({ scrollTop: $inFocus.offset().top - svgtop - window.innerHeight / 2 }, { duration: 'slow', easing: 'swing'});
          }
        }
        saveSVG();
        $('#waiter').dialog('close');
      }

      var onStartedRendering = function() {
        hideForm(fileBrowser);
        $('#waiter').dialog('open');
      }

      var showSVGDownloadLinks = function(data) {
        if (data && data.exception == 'corruptSVG') {
          dispatcher.post('messages', [[['Cannot save SVG: corrupt', 'error']]]);
          return;
        }
        var params = {
            action: 'retrieveSVG',
            'document': doc,
        };
        $('#download_svg_color').attr('href', 'ajax.cgi?' + $.param(params));
        params['version'] = 'greyscale';
        $('#download_svg_grayscale').attr('href', 'ajax.cgi?' + $.param(params));
        $('#download_svg').show();
      };

      var hideSVGDownloadLinks = function() {
        $('#download_svg').hide();
      };

      var onRenderData = function(_data) {
        if (_data && !_data.exception) {
          data = _data;
        }
        if (!data) return;
        var $sourceFiles = $('#source_files').empty();
        $.each(data.source_files, function(extNo, ext) {
          var $link = $('<a target="brat_search"/>').
              text(ext).
              attr('href',
                  'ajax.cgi?action=downloadFile&collection=' + coll +
                  '&document=' + doc + '&extension=' + ext);
          if (extNo) $sourceFiles.append(', ');
          $sourceFiles.append($link);
        });
        hideSVGDownloadLinks();

        if (data.mtime) {
          // we're getting seconds and need milliseconds
          //$('#document_ctime').text("Created: " + Annotator.formatTime(1000 * data.ctime)).css("display", "inline");
          $('#document_mtime').text("Last modified: " + Util.formatTimeAgo(1000 * data.mtime)).show();
        } else {
          //$('#document_ctime').css("display", "none");
          $('#document_mtime').hide();
        }
      }

      var gotCurrent = function(_coll, _doc, _args) {
        coll = _coll;
        doc = _doc;
        args = _args;

        $docName = $('#document_name input').val(coll + doc);
        var docName = $docName[0];
        // TODO do this on resize, as well
        // scroll the document name to the right, so the name is visible
        // (even if the collection name isn't, fully)
        docName.scrollLeft = docName.scrollWidth;

        $('#document_mtime').hide();
        hideSVGDownloadLinks();
      };

      var slideToggle = function(el, show) {
        var el = $(el);
        var height = el.data("cachedHeight");
        var visible = el.is(":visible");

        if (show === undefined) show = !visible;

        if (show === visible) return false;

        if (!height) {
          height = el.show().height();
          el.data("cachedHeight", height);
          if (!visible) el.hide().css({ height: 0 });
        }

        if (show) {
          el.show().animate({ height: height }, { duration: 150 });
        } else {
          el.animate({ height: 0 }, { duration: 300, complete: function() {
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
          $('#pulldownArrow').hide('fast');
        }).
        mouseleave(function(evt) {
          clearTimeout(menuTimer);
          menuTimer = setTimeout(function() {
            slideToggle($('#pulldown').stop(), false);
          }, 500);
        });

      $('#confirm_mode').click(function(evt) {
        var val = this.checked;
        if (val) {
          dispatcher.post('messages', [[['Confirm mode is now on', 'comment']]]);
        } else {
          dispatcher.post('messages', [[['Confirm mode is now off', 'comment']]]);
        }
      });

      $('#abbrev_mode').click(function(evt) {
        var val = this.checked;
        if (val) {
          dispatcher.post('messages', [[['Abbreviations are now on', 'comment']]]);
        } else {
          dispatcher.post('messages', [[['Abbreviations are now off', 'comment']]]);
        }
        dispatcher.post('abbrevs', [val]);
        dispatcher.post('resetData');
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
  	    width : 400,
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

          var spanText = data.text.substring(span.from, span.to);
          $('#viewspan_selected').text(spanText);
          var encodedText = encodeURIComponent(spanText);
          // TODO: DRY it off (it is almost-copy of annotator_ui)
          $('#viewspan_uniprot').attr('href', 'http://www.uniprot.org/uniprot/?sort=score&query=' + encodedText);
          $('#viewspan_entregene').attr('href', 'http://www.ncbi.nlm.nih.gov/gene?term=' + encodedText);
          $('#viewspan_wikipedia').attr('href', 'http://en.wikipedia.org/wiki/Special:Search?search=' + encodedText);
          $('#viewspan_google').attr('href', 'http://www.google.com/search?q=' + encodedText);
          $('#viewspan_alc').attr('href', 'http://eow.alc.co.jp/' + encodedText);

          // annotator comments
          $('#viewspan_notes').val(span.annotatorNotes || '');
          dispatcher.post('showForm', [viewspanForm]);
          $('#viewspan_form-ok').focus();
          adjustFormToCursor(evt, viewspanForm.parent());
        }
      };
      viewspanForm.submit(function(evt) {
        dispatcher.post('hideForm', [viewspanForm]);
        return false;
      });

      var authForm = $('#auth_form');
      initForm(authForm);
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
                $('#auth_button').val('Logout');
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
              auth_button.val('Logout');
              dispatcher.post('user', [user]);
              $('.login').show();
            } else {
              user = null;
              auth_button.val('Login');
              dispatcher.post('user', [null]);
              $('.login').hide();
            }
          }
        ]);
      };

      var showUnableToReadTextFile = function() {
        dispatcher.post('messages', [[['Unable to read the text file.', 'error']]]);
        showFileBrowser();
      };

      var showAnnotationFileNotFound = function() {
        dispatcher.post('messages', [[['Annotation file not found.', 'error']]]);
        showFileBrowser();
      };

      var showUnknownError = function(exception) {
        dispatcher.post('messages', [[['Unknown error: ' + exception, 'error']]]);
        showFileBrowser();
      };

      var reloadDirectoryWithSlash = function(data) {
        var collection = data.collection + data.document + '/';
        dispatcher.post('setCollection', [collection, '', data.arguments]);
      };

      var spanAndAttributeTypesLoaded = function(_spanTypes, _attributeTypes) {
        spanTypes = _spanTypes;
        attributeTypes = _attributeTypes;
      };

      var annotationIsAvailable = function() {
        annotationAvailable = true;
      };

      // hide anything requiring login, just in case
      $('.login').hide();

      dispatcher.
          on('init', init).
          on('annotationIsAvailable', annotationIsAvailable).
          on('messages', displayMessages).
          on('displaySpanComment', displaySpanComment).
          on('displayArcComment', displayArcComment).
          on('displaySentComment', displaySentComment).
          on('hideComment', hideComment).
          on('showForm', showForm).
          on('hideForm', hideForm).
          on('initForm', initForm).
          on('collectionLoaded', collectionLoaded).
          on('spanAndAttributeTypesLoaded', spanAndAttributeTypesLoaded).
          on('current', gotCurrent).
          on('doneRendering', onDoneRendering).
          on('startedRendering', onStartedRendering).
          on('renderData', onRenderData).
          on('savedSVG', showSVGDownloadLinks).
          on('renderError:noFileSpecified', showFileBrowser).
          on('renderError:annotationFileNotFound', showAnnotationFileNotFound).
          on('renderError:unableToReadTextFile', showUnableToReadTextFile).
          on('renderError:isDirectoryError', reloadDirectoryWithSlash).
          on('unknownError', showUnknownError).
          on('keydown', onKeyDown).
          on('mousemove', onMouseMove).
          on('dblclick', onDblClick).
          on('resize', onResize).
          on('searchResultsReceived', searchResultsReceived).
          on('clearSearch', clearSearch);
    };

    return VisualizerUI;
})(jQuery, window);
