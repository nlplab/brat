var Utility = (function(window, undefined) {

    var monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

    var unitAgo = function(n, unit) {
      if (n == 1) return "" + n + " " + unit + " ago";
      return "" + n + " " + unit + "s ago";
    };

    var formatTimeAgo = function(time) {
      if (time == -1000) {
        return "never"; // FIXME make the server return the server time!
      }

      var nowDate = new Date();
      var now = nowDate.getTime();
      var diff = Math.floor((now - time) / 1000);
      if (!diff) return "just now";
      if (diff < 60) return unitAgo(diff, "second");
      diff = Math.floor(diff / 60);
      if (diff < 60) return unitAgo(diff, "minute");
      diff = Math.floor(diff / 60);
      if (diff < 24) return unitAgo(diff, "hour");
      diff = Math.floor(diff / 24);
      if (diff < 7) return unitAgo(diff, "day");
      if (diff < 28) return unitAgo(Math.floor(diff / 7), "week");
      var thenDate = new Date(time);
      var result = thenDate.getDate() + ' ' + monthNames[thenDate.getMonth()];
      if (thenDate.getYear() != nowDate.getYear()) {
        result += ' ' + thenDate.getFullYear();
      }
      return result;
    }

    var realBBox = function(span) {
      var box = span.rect.getBBox();
      var chunkTranslation = span.chunk.translation;
      var rowTranslation = span.chunk.row.translation;
      box.x += chunkTranslation.x + rowTranslation.x;
      box.y += chunkTranslation.y + rowTranslation.y;
      return box;
    }

    return {
      formatTimeAgo: formatTimeAgo,
      realBBox: realBBox
    };
    
})(window);
