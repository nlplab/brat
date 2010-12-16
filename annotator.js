// make JS debugger-friendly
if (typeof(console) === 'undefined') {
  var console = {};
  console.log = console.error = console.info = console.debug =
      console.warn = console.trace = console.dir = console.dirxml =
      console.group = console.groupEnd = console.time =
      console.timeEnd = console.assert = console.profile =
      function() {};
}

// SVG Annotation tool
var Annotator = function(containerElement, onStart) {
  if (!Annotator.count) Annotator.count = 0;
  var id = Annotator.count;
  this.variable = "Annotator[" + id + "]";
  var annotator = Annotator[Annotator.count] = this;
  Annotator.count++;

  containerElement = $(containerElement);

  // settings
  var margin = { x: 5, y: 5 };
  var lineHeight = 60;
  var textSeparation = 40;
  var space = 5;
  var curlyHeight = 10;
  var topSpace = 50;

  var canvasWidth;
  var svg;
  var svgElement;
  var data;

  this.drawInitial = function(_svg) {
    svg = _svg;
    svgElement = $(svg._svg);
    if (onStart) onStart.call(annotator);
  }

  var Span = function(id, type, from, to) {
    this.id = id;
    this.type = type;
    this.from = from;
    this.to = to;
  }

  // event is reserved
  var EventDesc = function(id, triggerId, roles) {
    this.id = id;
    this.triggerId = triggerId;
    this.roles = roles;
  }

  var setData = function(_data) {
    if (!_data) return;
    data = _data;

    // collect annotation data
    data.spanOrder = [];
    data.spans = {};
    $.each(data.entities, function(entityNo, entity) {
      var span =
          new Span(entity[0], entity[1], entity[2], entity[3]);
      data.spans[entity[0]] = span;
      data.spanOrder.push(span);
    });
    var triggerHash = {};
    $.each(data.triggers, function(triggerNo, trigger) {
      triggerHash[trigger[0]] =
          new Span(trigger[0], trigger[1], trigger[2], trigger[3]);
    });
    data.eventDescs = {};
    $.each(data.events, function(eventNo, eventRow) {
      data.eventDescs[eventRow[0]] =
          new EventDesc(eventRow[0], eventRow[1], eventRow[2]);
      var span = $.extend({}, triggerHash[eventRow[1]]); // clone
      span.id = eventRow[0];
      data.spans[eventRow[0]] = span;
      data.spanOrder.push(span);
    });
    $.each(data.modifications, function(modNo, mod) {
      data.spans[mod[2]][mod[1]] = true;
    });

    // find chunk breaks
    var breaks = [[-1, false]];
    var pos = -1;
    while ((pos = data.text.indexOf('\n', pos + 1)) != -1) {
      breaks.push([pos, true]);
    }
    pos = -1;
    while ((pos = data.text.indexOf(' ', pos + 1)) != -1) {
      var wordBreak = true;
      // possible word break: see if it belongs to any spans
      $.each(data.spanOrder, function(spanNo, span) {
        if (span.from <= pos + data.offset && pos + data.offset < span.to) {
          // it does; no word break
          wordBreak = false;
          return false;
        }
      });
      if (wordBreak) breaks.push([pos, false]);
    }
    breaks.sort(function(a, b) { return a[0] - b[0] });

    // split text into chunks
    // format: data.chunks[chunk] = [text, from, to, lineBreak, [spans]]
    data.chunks = [];
    var numBreaks = breaks.length;
    breaks.push([data.text.length, false]);
    for (var breakNo = 0; breakNo < numBreaks; breakNo++) {
      var from = breaks[breakNo][0] + 1;
      var to = breaks[breakNo + 1][0];
      if (from != to) {
        data.chunks.push({
            text: data.text.substring(from, to),
            from: from + data.offset,
            to: to + data.offset,
            lineBreak: breaks[breakNo][1],
            spans: [],
          });
      }
    }

    // assign spans to appropriate chunks
    var numChunks = data.chunks.length;
    for (spanId in data.spans) {
      var span = data.spans[spanId];
      for (var j = 0; j < numChunks; j++) {
        var chunk = data.chunks[j];
        if (span.to <= chunk.to) {
          chunk.spans.push(span);
          break; // chunks
        }
      }
    }
  }

  var placeReservation = function(from, to, reservations) {
    var newSlot = { from: from, to: to };
    var resLen = reservations.length;
    for (var resNo = 0; resNo < resLen; resNo++) {
      var line = reservations[resNo];
      var overlap = false;
      $.each(line, function(j, slot) {
        if (slot.from <= to && from <= slot.to) {
          overlap = true;
          return false;
        }
      });
      if (!overlap) {
        line.push(newSlot);
        return resNo;
      }
    }
    reservations.push([newSlot]);
    return resLen;
  }

  var translate = function(element, x, y) {
    $(element.group).attr('transform', 'translate(' + x + ', ' + y + ')');
    element.translation = { x: x, y: y };
  }

  var Row = function() {
    this.group = svg.group();
    this.reservations = [];
    this.chunks = [];
  }

  var realBBox = function(span) {
    var box = span.rect.getBBox();
    var chunkTranslation = span.chunk.translation;
    var rowTranslation = span.chunk.row.translation;
    box.x += chunkTranslation.x + rowTranslation.x;
    box.y += chunkTranslation.y + rowTranslation.y;
    return box;
  }

  this.renderData = function(_data) {
    setData(_data);
    svg.clear();
    if (!data || data.length == 0) return;
    // FIXME for some reason, resizing does not work correctly
    canvasWidth = $(containerElement).width();
    $(svg).attr('width', canvasWidth);
    
    var current = { x: margin.x, y: topSpace };
    var lastNonText = { chunkInRow: -1, rightmostX: 0 }; // TODO textsqueeze
    var rows = [];
    var row = new Row();

    $.each(data.chunks, function(chunkNo, chunk) {
      chunk.reservations = [];
      chunk.group = svg.group(row.group);

      // a group for text highlight below the text
      chunk.highlightGroup = svg.group(chunk.group);

      svg.text(chunk.group, 0, 0, chunk.text);
      var y = -textSeparation;

      $.each(chunk.spans, function(spanNo, span) {
        span.chunk = chunk;
        span.group = svg.group(chunk.group, {
          'class': 'span',
        });

        // measure the text span
        var measureText = svg.text(chunk.group, 0, 0,
          chunk.text.substr(0, span.from - chunk.from));
        var xFrom = measureText.getBBox().width;
        svg.remove(measureText);
        measureText = svg.text(chunk.group, 0, 0,
          chunk.text.substr(0, span.to - chunk.from));
        var measureBox = measureText.getBBox();
        var xTo = measureBox.width;
        span.curly = {
          from: xFrom,
          to: xTo,
          y: measureBox.y,
          height: measureBox.height,
        };
        svg.remove(measureText);
        var x = (xFrom + xTo) / 2;

        var spanText = svg.text(span.group, x, y, span.type);
        var spanBox = spanText.getBBox();
        svg.remove(spanText);
        var dasharray = span.Speculation ? '3, 3' : 'none';
        span.rect = svg.rect(span.group,
          spanBox.x - margin.x,
          spanBox.y - margin.y,
          spanBox.width + 2 * margin.x,
          spanBox.height + 2 * margin.y, {
            'class': 'span_' + span.type,
            rx: margin.x,
            ry: margin.y,
            'data-span-id': span.id,
            'strokeDashArray': dasharray,
          });
        var rectBox = span.rect.getBBox();

        var line = placeReservation(
            rectBox.x, rectBox.x + rectBox.width, chunk.reservations);
        var yAdjust = line * lineHeight;
        $(span.rect).attr('y', spanBox.y - margin.y - yAdjust);
        $(spanText).attr('y', y - yAdjust);
        if (span.Negation) {
          svg.path(span.group, svg.createPath().
              move(spanBox.x, spanBox.y - margin.y - yAdjust).
              line(spanBox.x + spanBox.width,
                spanBox.y + spanBox.height + margin.y - yAdjust),
              { 'class': 'negation' });
          svg.path(span.group, svg.createPath().
              move(spanBox.x + spanBox.width, spanBox.y - margin.y - yAdjust).
              line(spanBox.x, spanBox.y + spanBox.height + margin.y - yAdjust),
              { 'class': 'negation' });
        }
        svg.add(span.group, spanText);

        // Make curlies to show the span
        var bottom = spanBox.y + spanBox.height + margin.y - yAdjust;
        svg.path(span.group, svg.createPath()
            .move(xFrom, bottom + curlyHeight)
            .curveC(xFrom, bottom,
              x, bottom + curlyHeight,
              x, bottom)
            .curveC(x, bottom + curlyHeight,
              xTo, bottom,
              xTo, bottom + curlyHeight),
          {
        });
      }); // spans

      // positioning of the chunk
      var chunkBox = chunk.group.getBBox();
      if (chunk.lineBreak
          || current.x + chunkBox.width >= canvasWidth - 2 * margin.x) {
        // new row
        var rowBox = row.group.getBBox();
        translate(row, 0, current.y - rowBox.y);
        rows.push(row);
        current.y += rowBox.height + textSeparation;
        current.x = margin.x;
        svg.remove(chunk.group);
        lastNonText = { chunkInRow: -1, rightmostX: 0 }; // TODO textsqueeze
        row = new Row();
        svg.add(row.group, chunk.group);
        chunk.group = row.group.lastElementChild;
        $(chunk.group).children("g[class='span']").
          each(function(index, element) {
              chunk.spans[index].group = element;
          });
        $(chunk.group).find("rect").
          each(function(index, element) {
              chunk.spans[index].rect = element;
          });
        chunk.highlightGroup = chunk.group.firstElementChild;
      }
      row.chunks.push(chunk);
      chunk.row = row;
      translate(chunk, current.x - chunkBox.x, 0);

      // translate individual chunk reservations
      var xShift = chunk.translation.x;
      $.each(chunk.reservations, function(line, lineReservations) {
        if (!row.reservations[line]) row.reservations[line] = [];
        $.each(lineReservations, function(j, res) {
          row.reservations[line].push(
            { from: res.from + xShift, to: res.to + xShift });
        }); // lineReservations
      }); // chunk.reservations
      current.x += chunkBox.width + space;
    }); // chunks

    // finish the last row
    var rowBox = row.group.getBBox();
    translate(row, 0, current.y - rowBox.y);
    rows.push(row);

    // resize the SVG
    current.y += rowBox.height + margin.y;
    $(svg._svg).attr('height', current.y).css('height', current.y);
    $(containerElement).attr('height', current.y).css('height', current.y);

    var arcs = svg.group({ 'class': 'arc' });
    var defs = svg.defs();
    var arrows = {};

    // add the events
    $.each(data.eventDescs, function(eventId, eventDesc) {
      $.each(eventDesc.roles, function(j, role) {
        var roleType = role[0];
        var roleId = role[1];
        roleClass = 'role_' + roleType;

        if (!arrows[roleType]) {
          var arrowId = 'annotator' + id + '_arrow_' + roleType;
          var arrowhead = svg.marker(defs, arrowId,
            5, 2.5, 5, 5, 'auto',
            {
              markerUnits: 'strokeWidth',
              'class': 'fill_' + roleType,
            });
          svg.polyline(arrowhead, [[0, 0], [5, 2.5], [0, 5], [0.2, 2.5]]);

          arrows[roleType] = arrowId;
        }

        var triggerSpan = data.spans[eventDesc.id];
        var roleSpan = data.spans[roleId];

        var triggerBox = realBBox(triggerSpan);
        var roleBox = realBBox(roleSpan);
        var leftToRight = triggerBox.x < roleBox.x;
        var role = {
          span: roleSpan,
          box: roleBox,
        };
        var trigger = {
          span: triggerSpan,
          box: triggerBox,
        };
        var displacement = triggerBox.width / 4;
        var sign = leftToRight ? 1 : -1;

        var startX = 
            trigger.box.x + trigger.box.width / 2 + sign * displacement;
        var endX =
            role.box.x + role.box.width / 2;
        var midX1 = (3 *
          (trigger.box.x + trigger.box.width / 2 + sign * displacement) +
          role.box.x + role.box.width / 2) / 4;
        var midX2 = (
          trigger.box.x + trigger.box.width / 2 + sign * displacement +
          3 * (role.box.x + role.box.width / 2)) / 4;
        var pathId = 'annotator' + id + '_path_' + eventId + '_' + roleType;
        var path = svg.createPath().move(
            startX, trigger.box.y
          ).curveC(
            midX1, trigger.box.y - 50,
            midX2, role.box.y - 50,
            endX, role.box.y
          );
        var group = svg.group(arcs,
            { 'data-from': eventDesc.id, 'data-to': roleId });
        svg.path(group, path, {
            markerEnd: 'url(#' + arrows[roleType] + ')',
            id: leftToRight ? pathId : undefined,
            'class': 'stroke_' + roleType,
        });
        if (!leftToRight) {
          path = svg.createPath().move(
              endX, role.box.y
            ).curveC(
              midX2, role.box.y - 50,
              midX1, trigger.box.y - 50,
              startX, trigger.box.y
            );
          svg.path(group, path, {
              stroke: 'none',
              id: pathId,
          });
        }
        var text = svg.text(group, '');
        svg.textpath(text, '#' + pathId, svg.createText().string(roleType),
          {
            'class': 'fill_' + roleType,
            startOffset: '50%',
          });
      });
    });

    var highlight;
    var highlightArcs;

    this.mouseOver = function(evt) {
      var target = $(evt.target);
      var id;
      if (id = target.attr('data-span-id')) {
        var span = data.spans[id];
        highlight = svg.rect(span.chunk.highlightGroup,
          span.curly.from - 1, span.curly.y - 1,
          span.curly.to + 2 - span.curly.from, span.curly.height + 2,
          { 'class': 'span_' + span.type });
        highlightArcs = target.closest('svg').find('.arc').
          children('g[data-from="' + id + '"], g[data-to="' + id + '"]');
        highlightArcs.addClass('highlight');
      }
    };

    this.mouseOut = function(evt) {
      if (highlight) {
        svg.remove(highlight);
        highlight = null;
      }
      if (highlightArcs) {
        highlightArcs.removeClass('highlight');
      }
    };
  }

  containerElement.svg({
      onLoad: this.drawInitial,
      settings: {
          onmouseover: this.variable + ".mouseOver(evt)",
          onmouseout: this.variable + ".mouseOut(evt)",
      /*
          onmousedown: this.variable + ".mouseDown(evt)",
          onmousemove: this.variable + ".mouseMove(evt)",
          onmouseup: this.variable + ".mouseUp(evt)",
      */
      }
  });
};

$(function() {
  var address = window.location.href;
  if (!window.location.hash.substr(1)) return;
  var directory = window.location.hash.substr(1).split('/')[0];
  var doc;
  var lastDoc = null;
  var qmark = address.indexOf('#');
  var slashmark = address.lastIndexOf('/', qmark);
  var base = address.slice(0, slashmark + 1);
  var ajaxURL = base + "ajax.cgi?directory=" + directory;


  $.get(ajaxURL, function(data) {
    $('#document_select').html(data).val(doc);
  });

  var annotator = new Annotator('#svg', function() {
    var annotator = this;

    var lastHash = null;
    var directoryAndDoc;
    var drawing = false;
    var updateState = function() {
      if (drawing || lastHash == window.location.hash) return;
      lastHash = window.location.hash;
      var parts = lastHash.substr(1).split('/');
      directory = parts[0];
      doc = parts[1];
      $('#document_select').val(doc);

      $('#document_name').text(directoryAndDoc);
      $.get(ajaxURL + "&document=" + doc, function(data) {
          drawing = true;
          annotator.renderData(data);
          drawing = false;
      });
    }

    setInterval(updateState, 200); // TODO okay?

    var renderSelected = function(evt) {
      doc = $('#document_select').val();
      directoryAndDoc = directory + (doc ? '/' + doc : '');
      window.location.hash = '#' + directoryAndDoc;
      updateState();
      return false;
    };

    $('#document_form').
        submit(renderSelected).
        children().
        removeAttr('disabled');

    $('#document_select').
        change(renderSelected);

    directoryAndDoc = directory + (doc ? '/' + doc : '');
    updateState(doc);
  });

  $(window).resize(function(evt) {
    annotator.renderData();
  });
});
