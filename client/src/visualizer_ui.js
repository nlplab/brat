var VisualizerUI = (function($, window, undefined) {
    var VisualizerUI = function(dispatcher) {
      var that = this;

      var messagePostOutFadeDelay = 1000;
      var messageDefaultFadeDelay = 3000;
      var defaultFloatFormat = '%.1f/right';

      var filesData = null;
      var currentForm;
      var dir, doc, args;
      var dirScroll;
      var docScroll;

      var sortOrder = [1, 1]; // column (0..), sort order (1, -1)
      var docSortFunction = function(a, b) {
          // parent dir at the top
          if (a[1] === '..') return -1;
          if (b[1] === '..') return 1;

          // then other directories
          var aa = a[0];
          var bb = b[0];
          if (aa !== bb) return aa ? -1 : 1;

          // desired column in the desired order
          var col = sortOrder[0];
          var aa = a[col];
          var bb = b[col];
          if (aa != bb) return (aa < bb) ? -sortOrder[1] : sortOrder[1];

          // prevent random shuffles on columns with duplicate values
          // (alphabetical order of filenames)
          aa = a[1];
          bb = b[1];
          if (aa != bb) return (aa < bb) ? -1 : 1;
          return 0;
      };

      var makeSortChangeFunction = function(sort, th, thNo) {
          $(th).click(function() {
              if (sort[0] === thNo + 1) sort[1] = -sort[1];
              else {
                var type = filesData.dochead[thNo][1];
                var ascending = type === "string";
                sort[0] = thNo + 1;
                sort[1] = ascending ? 1 : -1;
              }
              showFileBrowser(); // resort
          });
      }

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

      var adjustToCursor = function(evt, element, offset, top, right) {
        // get the real width, without wrapping
        element.css({ left: 0, top: 0 });
        var screenHeight = $(window).height();
        var screenWidth = $(window).width();
        // FIXME why the hell is this 22 necessary?!?
        var elementHeight = element.height() + 22;
        var elementWidth = element.width() + 22;
        var x, y;
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
        element.css({ top: y, left: x });
      };

      var infoPopup = $('#infopopup');
      var infoDisplayed = false;

      var displayInfo = function(evt, target, info, infoText, infoType) {
        var idtype;
        if (infoType) {
          info += infoText;
          idtype = 'info_' + infoType;
        }
        infoPopup[0].className = idtype;
        infoPopup.html(info);
        adjustToCursor(evt, infoPopup, 10, true, true);
        infoPopup.stop(true, true).fadeIn();
        infoDisplayed = true;
      };

      var displaySpanInfo = function(
          evt, target, spanId, spanType, mods, spanText, infoText, infoType) {

        var info = '<div><span class="info_id">' + spanId + '</span>' +
          ' ' + '<span class="info_type">' + spanType + '</span>';
        if (mods.length) {
          info += '<div>' + mods.join(', ') + '</div>';
        }
        info += '</div>';
        info += '<div>"' + spanText + '"</div>';
        displayInfo(evt, target, info, infoText, infoType);
      };

      var displayArcInfo = function(
          evt, target, symmetric,
          originSpanId, role, targetSpanId, infoText, infoType) {
        var info = (symmetric
          ? '<div class="info_arc">' + originSpanId + ' ' +
            target.attr('data-arc-role') + ' ' + targetSpanId +'</div>'
          : '<div class="info_arc">' + originSpanId + ' &#8594; ' +
            target.attr('data-arc-role') + ':' + targetSpanId +'</div>');
        displayInfo(evt, target, info, infoText, infoType);
      };

      var displaySentInfo = function(
          evt, target, infoText, infoType) {
        displayInfo(evt, target, '', infoText, infoType);
      };

      var hideInfo = function() {
        infoPopup.stop(true, true).fadeOut(function() { infoDisplayed = false; });
      };

      var onMouseMove = function(evt) {
        if (infoDisplayed) {
          adjustToCursor(evt, infoPopup, 10, true, true);
        }
      };

      initForm = function(form, opts) {
        opts = opts || {};
        var formId = form.attr('id');

        // alsoResize is special
        var alsoResize = opts.alsoResize;
        delete opts.alsoResize;

        // Always add OK and Cancel
        var buttons = (opts.buttons || []).concat([
            {
              id: formId + "-ok",
              text: "OK",
              click: function() { form.submit(); }
            },
            {
              id: formId + "-cancel",
              text: "Cancel",
              click: function() { form.dialog('close'); }
            },
          ]);
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
        form.dialog('open');
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
        fileBrowserSubmit();
      }

      var fileBrowser = $('#file_browser');
      initForm(fileBrowser, {
          alsoResize: '#document_select',
          close: function(evt) {
            if (!doc) {
              $('#waiter').dialog('close');
            }
          },
          width: 500
      });
      //fileBrowser.widget().resizable('option', 'alsoResize', '#document_select');
      $('#document_input').change(function(evt) {
        selectElementInTable('#document_select', $(this).val());
      });
      var fileBrowserSubmit = function(evt) {
        var _dir, _doc, found;
        var input = $('#document_input').
            val().
            replace(/\/?\\s+$/, '').
            replace(/^\s+/, '');
        if (input.substr(0, 2) === '..') {
          // ..
          var pos = dir.substr(0, dir.length - 1).lastIndexOf('/');
          if (pos === -1) {
            dispatcher.post('messages', [[['At the top directory', 'error', 2]]]);
            $('#document_input').focus().select();
            return false;
          } else {
            _dir = dir.substr(0, pos + 1);
            _doc = '';
          }
        } else if (found = input.match(/^(\/?)((?:[^\/]+\/)*)([^\/]*)$/)) {
          var abs = found[1];
          var dirname = found[2].substr(0, found[2].length - 1);
          var docname = found[3];
          if (abs) {
            _dir = abs + dirname;
            if (_dir.length < 2) dir += '/';
            _doc = docname;
          } else {
            if (dirname) dirname += '/';
            _dir = dir + dirname;
            _doc = docname;
          }
        } else {
          dispatcher.post('messages', [[['Invalid document name format', 'error', 2]]]);
          $('#document_input').focus().select();
        }
        dispatcher.post('setDirectory', [_dir, _doc]);
        docScroll = $('#document_select')[0].scrollTop;
        fileBrowser.find('#document_select tbody').html(''); // prevent a slowbug
        return false;
      };
      fileBrowser.
          submit(fileBrowserSubmit).
          bind('reset', hideForm);
      var showFileBrowser = function() {
        if (!(filesData && showForm(fileBrowser))) return false;

        var html = ['<tr>'];
        var tbody;
        $.each(filesData.dochead, function(headNo, head) {
          html.push('<th>' + head[0] + '</th>');
        });
        html.push('</tr>');
        $('#document_select thead').html(html.join(''));

        html = [];
        filesData.docs.sort(docSortFunction);
        $.each(filesData.docs, function(docNo, doc) {
          var isDir = doc[0];
          var name = doc[1];
          var dirFile = isDir ? 'dir' : 'file';
          var dirSuffix = isDir ? '/' : '';
          html.push('<tr class="' + dirFile + '" data-value="'
              + name + dirSuffix + '"><th>' + name + dirSuffix + '</th>');
          var len = filesData.dochead.length - 1;
          for (var i = 0; i < len; i++) {
            var type = filesData.dochead[i + 1][1];
            var datum = doc[i + 2];
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
              formatted = Utility.formatTimeAgo(datum * 1000);
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

        $('#directory_input').val(filesData.directory);
        $('#document_input').val(doc);
        var curdir = filesData.directory;
        var pos = curdir.lastIndexOf('/');
        if (pos != -1) curdir = curdir.substring(pos + 1);
        selectElementInTable($('#directory_select'), curdir);
        selectElementInTable($('#document_select'), doc);
        setTimeout(function() {
          $('#document_input').focus().select();
        }, 0);
      };
      $('#file_browser_button').click(showFileBrowser);

      var onKeyDown = function(evt) {
        var code = evt.which;

        if (code === $.ui.keyCode.ESCAPE) {
          dispatcher.post('messages', [false]);
          return;
        }

        if (currentForm) {
          if (code === $.ui.keyCode.ENTER) {
            currentForm.trigger('submit');
          }
          return;
        }

        if (code === $.ui.keyCode.TAB) {
          showFileBrowser();
          return false;
        } else if (code == $.ui.keyCode.LEFT) {
          var pos;
          $.each(filesData.docs, function(docNo, docRow) {
            if (docRow[1] === doc) {
              pos = docNo;
              return false;
            }
          });
          if (pos > 0 && !filesData.docs[pos - 1][0]) {
            // not at the start, and the previous is not a directory
            dispatcher.post('setDocument', [filesData.docs[pos - 1][1]]);
          }
          return false;
        } else if (code === $.ui.keyCode.RIGHT) {
          var pos;
          $.each(filesData.docs, function(docNo, docRow) {
            if (docRow[1] == doc) {
              pos = docNo;
              return false;
            }
          });
          if (pos < filesData.docs.length - 1) {
            // not at the end
            dispatcher.post('setDocument', [filesData.docs[pos + 1][1]]);
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

      var dirLoaded = function(response) {
        if (response.exception) {
          dispatcher.post('setDirectory', ['/']);
        } else {
          filesData = response;
        }
      };

      var saveSVGTimer = null;
      var saveSVG = function() {
        clearTimeout(saveSVGTimer);
        saveSVGTimer = dispatcher.post(500, 'ajax', [{
          action: 'storeSVG',
          svg: $('#svg').html()
        }, 'savedSVG']);
      };

      var onDoneRendering = function() {
        saveSVG();
        $('#waiter').dialog('close');
      }

      var onStartedRendering = function() {
        hideForm(fileBrowser);
        $('#waiter').dialog('open');
      }

      var showSVGDownloadLinks = function(data) {
        var params = {
            action: 'retrieveSVG',
            'document': doc,
            version: 'colour'
        };
        $('#download_svg_color').attr('href', 'ajax.cgi?' + $.param(params));
        params['version'] = 'greyscale';
        $('#download_svg_grayscale').attr('href', 'ajax.cgi?' + $.param(params));
        $('#download_svg').show();
      };

      var hideSVGDownloadLinks = function() {
        $('#download_svg').hide();
      };

      var gotCurrent = function(_dir, _doc, _args) {
        dir = _dir;
        doc = _doc;
        args = _args;
        $('#document_name').text(dir + doc);
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
          dispatcher.post('messages', [[['Confirm mode is now on', 'info']]]);
        } else {
          dispatcher.post('messages', [[['Confirm mode is now off', 'info']]]);
        }
      });

      $('#abbrev_mode').click(function(evt) {
        var val = this.checked;
        if (val) {
          dispatcher.post('messages', [[['Abbreviations are now on', 'info']]]);
        } else {
          dispatcher.post('messages', [[['Abbreviations are now off', 'info']]]);
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
              }
          });
      $('#mainlogo').click(function() {
        showForm(aboutDialog);
      });

      dispatcher.
          on('messages', displayMessages).
          on('displaySpanInfo', displaySpanInfo).
          on('displayArcInfo', displayArcInfo).
          on('displaySentInfo', displaySentInfo).
          on('hideInfo', hideInfo).
          on('showForm', showForm).
          on('hideForm', hideForm).
          on('initForm', initForm).
          on('dirLoaded', dirLoaded).
          on('current', gotCurrent).
          on('doneRendering', onDoneRendering).
          on('startedRendering', onStartedRendering).
          on('renderData', hideSVGDownloadLinks).
          on('savedSVG', showSVGDownloadLinks).
          on('noFileSpecified', showFileBrowser).
          on('keydown', onKeyDown).
          on('mousemove', onMouseMove).
          on('resize', onResize);

    };

    return VisualizerUI;
})(jQuery, window);
