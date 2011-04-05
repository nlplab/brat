var AnnotatorUI = (function($, window, undefined) {
    var AnnotatorUI = function(dispatcher) {
      var that = this;
      var arcDragOrigin = null;
      var arcDragOriginGroup = null;
      var selectedRange = null;

      that.user = null; // TODO autologin

      var onKeyPress = function(evt) {
        var char = evt.which;
      };

      var onMouseDown = function(evt) {
        var target = $(evt.target);
        // TODO
      };

      var onMouseUp = function(evt) {
      };

      var getUser = function() {
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

      dispatcher.
        on('init', getUser).
        on('keypress', onKeyPress).
        on('mousedown', onMouseDown).
        on('mouseup', onMouseUp);
    };

    return AnnotatorUI;
})(jQuery, window);
