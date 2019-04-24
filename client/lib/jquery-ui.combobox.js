/* Adapted from http://jqueryui.com/autocomplete/#combobox */
/* and http://www.learningjquery.com/2010/06/a-jquery-ui-combobox-under-the-hood/ */

(function($) {
  $.widget( "ui.combobox", {
    _create: function() {
      var self = this;
      var select = this.element.hide(),
        selected = select.children( ":selected" ),
        value = selected.val() ? selected.text() : "";
      var input = $( "<input />" )
        .insertAfter(select)
        .addClass("ui-combobox-input ui-state-default")
        .focus(function() {
          input.removeClass('ui-state-default');
          input.autocomplete("search", "");
        })
        .blur(function() {
          input.addClass('ui-state-default');
        })
        .val( value )
        .keydown(function(evt) {
          var text, start;
          if (evt.keyCode == $.ui.keyCode.BACKSPACE
              && (start = input[0].selectionStart) > 0
              && (end = input[0].selectionEnd) != start
              && end == (text = input.val()).length) {
            input.val(text = text.substring(0, start - 1));
            evt.preventDefault();
            return false;
          }
        })
        .autocomplete({
          delay: 0,
          minLength: 0,
          source: function(request, response) {
            var matcher = new RegExp( "^" + $.ui.autocomplete.escapeRegex(request.term), "i" );
            options = select.children("option").map(function() {
              var text = $( this ).text();
              if ( this.value && ( !request.term || matcher.test(text) ) )
                return {
                  label: text.replace(
                    new RegExp(
                      "(?![^&;]+;)(?!<[^<>]*)(" +
                      $.ui.autocomplete.escapeRegex(request.term) +
                      ")(?![^<>]*>)(?![^&;]+;)", "gi"),
                    "<strong>$1</strong>"),
                  value: text,
                  option: this
                };
            });
            response(options);
            if (request.term.length && options.length) {
              var text = options[0].value;
              input.val(text);
              input[0].selectionStart = request.term.length;
              input[0].selectionEnd = text.length;
              options[0].option.selected = true;
            } else {
              select.val('');
            }
          },
          select: function( event, ui ) {
            ui.item.option.selected = true;
            self._trigger( "selected", event, {
              item: ui.item.option
            });
          },
          change: function(event, ui) {
            if ( !ui.item ) {
              var valid = false;
              findMatch = function(matcher) {
                select.children( "option" ).each(function() {
                  if ( this.value.match( matcher ) ) {
                    this.selected = valid = true;
                    input.val(this.value);
                    return false;
                  }
                });
              };
              var escapedMatcher = $.ui.autocomplete.escapeRegex( $(this).val() );
              findMatch(new RegExp( "^" + escapedMatcher + "$", "i" ));
              if ( !valid ) {
                findMatch(new RegExp( "^" + escapedMatcher, "i" ));
              }
              if ( !valid ) {
                // remove invalid value, as it didn't match anything
                $( this ).val( "" );
                select.val( "" );
                return false;
              }
            }
          }
        })
        .addClass("ui-widget ui-widget-content ui-corner-all ui-combobox");
     
      input.data( "ui-autocomplete" )._renderItem = function( ul, item ) {
          return $( "<li></li>" )
            .data( "item.autocomplete", item )
            .append( "<a>" + item.label + "</a>" )
            .appendTo( ul );
        };

      select.change(function(evt) {
        input.val(select.val());
      });
    }
  });
})(jQuery);
/*
(function( $ ) {
  $.widget( "custom.combobox", {
    _create: function() {
      this.wrapper = $( "<span>" )
        .addClass( "custom-combobox" )
        .insertAfter( this.element );

      this.element.hide();
      this._createAutocomplete();
      this._createShowAllButton();
    },

    _createAutocomplete: function() {
      var selected = this.element.children( ":selected" ),
        value = selected.val() ? selected.text() : "";

      this.input = $( "<input>" )
        .appendTo( this.wrapper )
        .val( value )
        .attr( "title", "" )
        .addClass( "custom-combobox-input ui-widget ui-widget-content ui-state-default ui-corner-left" )
        .autocomplete({
          delay: 0,
          minLength: 0,
          source: $.proxy( this, "_source" )
        // })
        // .tooltip({
        //   tooltipClass: "ui-state-highlight"
        });

      // this._on( this.input, {
      $( this.input ).on({
        autocompleteselect: function( event, ui ) {
          ui.item.option.selected = true;
          $( this ).trigger( "select", event, {
            item: ui.item.option
          });
        },

        autocompletechange: this._removeIfInvalid.bind(this)
      });
    },

    _createShowAllButton: function() {
      var input = this.input,
        wasOpen = false;

      $( "<a>" )
        .attr( "tabIndex", -1 )
        .attr( "title", "Show All Items" )
        // .tooltip()
        .appendTo( this.wrapper )
        .button({
          icons: {
            primary: "ui-icon-triangle-1-s"
          },
          text: false
        })
        .removeClass( "ui-corner-all" )
        .addClass( "custom-combobox-toggle ui-corner-right" )
        .mousedown(function() {
          wasOpen = input.autocomplete( "widget" ).is( ":visible" );
        })
        .click(function() {
          input.focus();

          // Close if already visible
          if ( wasOpen ) {
            return;
          }

          // Pass empty string as value to search for, displaying all results
          input.autocomplete( "search", "" );
        });
    },

    _source: function( request, response ) {
      var matcher = new RegExp( $.ui.autocomplete.escapeRegex(request.term), "i" );
      response( this.element.children( "option" ).map(function() {
        var text = $( this ).text();
        if ( this.value && ( !request.term || matcher.test(text) ) )
          return {
            label: text,
            value: text,
            option: this
          };
      }) );
    },

    _removeIfInvalid: function( event, ui ) {

      // Selected an item, nothing to do
      if ( ui.item ) {
        return;
      }

      // Search for a match (case-insensitive)
      var value = this.input.val(),
        valueLowerCase = value.toLowerCase(),
        valid = false;
      this.element.children( "option" ).each(function() {
        if ( $( this ).text().toLowerCase() === valueLowerCase ) {
          this.selected = valid = true;
          return false;
        }
      });

      // Found a match, nothing to do
      if ( valid ) {
        return;
      }

      // Remove invalid value
      this.input
        .val( "" );
        // .attr( "title", value + " didn't match any item" )
        // .tooltip( "open" );
      this.element.val( "" );
      // $(this).delay(function() {
      //   this.input.tooltip( "close" ).attr( "title", "" );
      // }, 2500 );
      console.log(this.input);
      console.log(this.input.data('ui-autocomplete'));
      this.input.data( "ui-autocomplete" ).term = ""; // TODO
    },

    _destroy: function() {
      this.wrapper.remove();
      this.element.show();
    }
  });
})( jQuery );
*/
