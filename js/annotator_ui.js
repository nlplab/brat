var AnnotatorUI = (function($, window, undefined) {
    var AnnotatorUI = function(dispatcher) {
      var that = this;

      var onKeyPress = function(evt) {
        var char = evt.which;
      };

      var onKeyPress = function(evt) {
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
        on('keypress', onKeyPress);
    };

    return AnnotatorUI;
})(jQuery, window);
