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
  var margin = { x: 2, y: 1 };
  var space = 5;
  var boxSpacing = 3;
  var curlyHeight = 6;
  var lineSpacing = 5;

  var canvasWidth;
  var svg;
  var svgElement;
  var data;

  var highlight;
  var highlightArcs;

  var mouseOver = function(evt) {
    var target = $(evt.target);
    var id;
    if (id = target.attr('data-span-id')) {
      var span = data.spans[id];
      highlight = svg.rect(span.chunk.highlightGroup,
        span.curly.from - 1, span.curly.y - 1,
        span.curly.to + 2 - span.curly.from, span.curly.height + 2,
        { 'class': 'span_default span_' + span.type });
      highlightArcs = target.closest('svg').find('.arc').
        children('g[data-from="' + id + '"], g[data-to="' + id + '"]');
      highlightArcs.addClass('highlight');
    }
  };

  var mouseOut = function(evt) {
    if (highlight) {
      svg.remove(highlight);
      highlight = null;
    }
    if (highlightArcs) {
      highlightArcs.removeClass('highlight');
    }
  };

  this.drawInitial = function(_svg) {
    svg = _svg;
    svgElement = $(svg._svg);
    if (onStart) onStart.call(annotator);

    containerElement.mouseover(mouseOver);
    containerElement.mouseout(mouseOut);
  }

  var Span = function(id, type, from, to) {
    this.id = id;
    this.type = type;
    this.from = from;
    this.to = to;
    this.outgoing = [];
    this.incoming = [];
    this.totalDist = 0;
    this.numArcs = 0;
  }

  // event is reserved
  var EventDesc = function(id, triggerId, roles) {
    this.id = id;
    this.triggerId = triggerId;
    var roleList = this.roles = [];
    $.each(roles, function(roleNo, role) {
      roleList.push({ type: role[0], targetId: role[1] });
    });
  }

  var setData = function(_data) {
    if (!_data) return;
    data = _data;

    // collect annotation data
    data.spans = {};
    $.each(data.entities, function(entityNo, entity) {
      var span =
          new Span(entity[0], entity[1], entity[2], entity[3]);
      data.spans[entity[0]] = span;
    });
    var triggerHash = {};
    $.each(data.triggers, function(triggerNo, trigger) {
      triggerHash[trigger[0]] =
          new Span(trigger[0], trigger[1], trigger[2], trigger[3]);
    });
    data.eventDescs = {};
    $.each(data.events, function(eventNo, eventRow) {
      var eventDesc = data.eventDescs[eventRow[0]] =
          new EventDesc(eventRow[0], eventRow[1], eventRow[2]);
      var span = $.extend({}, triggerHash[eventDesc.triggerId]); // clone
      span.id = eventDesc.id;
      data.spans[eventDesc.id] = span;
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
      $.each(data.spans, function(spanNo, span) {
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
    var chunkNo = 0;
    for (var breakNo = 0; breakNo < numBreaks; breakNo++) {
      var from = breaks[breakNo][0] + 1;
      var to = breaks[breakNo + 1][0];
      if (from != to) {
        data.chunks.push({
            text: data.text.substring(from, to),
            from: from + data.offset,
            to: to + data.offset,
            lineBreak: breaks[breakNo][1],
            index: chunkNo++,
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
          span.chunk = chunk;
          break; // chunks
        }
      }
    }
   
    // assign arcs to spans; calculate arc distances
    data.arcs = [];
    $.each(data.eventDescs, function(eventNo, eventDesc) {
      var dist = 0;
      var origin = data.spans[eventDesc.id];
      var here = origin.chunk.index;
      $.each(eventDesc.roles, function(roleNo, role) {
        var target = data.spans[role.targetId];
        var there = target.chunk.index;
        var dist = Math.abs(here - there);
        var arc = {
          origin: eventDesc.id,
          target: role.targetId,
          dist: dist,
          type: role.type,
          jumpHeight: 0,
        };
        origin.totalDist += dist;
        origin.numArcs++;
        target.totalDist += dist;
        target.numArcs++;
        data.arcs.push(arc);
        // TODO: do we really need incoming and outgoing, if we have
        // totalDist?
        target.incoming.push(arc);
        origin.outgoing.push(arc);
      });
    });

    // sort spans in chunks
    data.spanLine = [];
    var spanNo = -1;
    var lastSpan = null;
    $.each(data.chunks, function(chunkNo, chunk) {
      $.each(chunk.spans, function(spanNo, span) {
        span.avgDist = span.totalDist / span.numArcs;
      });
      chunk.spans.sort(function(a, b) {
        // longer arc distances go last
        var tmp = a.avgDist - b.avgDist;
        if (tmp) {
          return tmp < 0 ? -1 : 1;
        }
        // if arc widths same, compare the span widths,
        // put wider on bottom so they don't mess with arcs
        var ad = a.to - a.from;
        var bd = b.to - b.from;
        tmp = ad - bd;
        if (tmp) {
          return tmp < 0 ? 1 : -1;
        }
        // lastly, all else being equal, earlier-starting ones go first
        tmp = a.from != b.from;
        if (tmp) {
          return tmp < 0 ? -1 : 1;
        }
        return 0;
      });
      // number the spans so we can check for heights later
      $.each(chunk.spans, function(i, span) {
        if (!lastSpan || (lastSpan.from != span.from || lastSpan.to != span.to)) {
          spanNo++;
          data.spanLine[spanNo] = []
          span.drawCurly = true;
        }
        data.spanLine[spanNo].push(span);
        span.lineIndex = spanNo;
        lastSpan = span;
      });
    });
  }

  var placeReservation = function(span, box, reservations) {
    var newSlot = {
      from: box.x,
      to: box.x + box.width,
      span: span,
      height: box.height + (span.drawCurly ? curlyHeight : 0),
    };
    var height = 0;
    if (reservations.length) {
      $.each(reservations, function(resNo, reservation) {
        var line = reservation.ranges;
        height = reservation.height;
        var overlap = false;
        $.each(line, function(j, slot) {
          if (slot.from <= newSlot.to && newSlot.from <= slot.to) {
            overlap = true;
            return false;
          }
        });
        if (!overlap) {
          if (!reservation.curly && span.drawCurly) {
            // TODO: need to push up the boxes drawn so far
            // (rare glitch)
          }
          line.push(newSlot);
          return height;
        }
      });
      height += newSlot.height + boxSpacing; 
    }
    reservations.push({
      ranges: [newSlot],
      height: height,
      curly: span.drawCurly,
    });
    return height;
  }

  var translate = function(element, x, y) {
    $(element.group).attr('transform', 'translate(' + x + ', ' + y + ')');
    element.translation = { x: x, y: y };
  }

  var Row = function() {
    this.group = svg.group();
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
    canvasWidth = $(containerElement).width();
    $(svg).attr('width', canvasWidth);
    
    var current = { x: margin.x, y: margin.y };
    var lastNonText = { chunkInRow: -1, rightmostX: 0 }; // TODO textsqueeze
    var rows = [];
    var spanHeights = [];
    var row = new Row();
    var textHeight;
    var reservations;

    $.each(data.chunks, function(chunkNo, chunk) {
      reservations = new Array();
      chunk.group = svg.group(row.group);

      // a group for text highlight below the text
      chunk.highlightGroup = svg.group(chunk.group);

      var chunkText = svg.text(chunk.group, 0, 0, chunk.text);
      if (!textHeight) {
        textHeight = chunkText.getBBox().height;
      }
      var y = 0;

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
        if (!y) y = -textHeight - curlyHeight;
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
            'class': 'span_' + span.type + ' span_default',
            rx: margin.x,
            ry: margin.y,
            'data-span-id': span.id,
            'strokeDashArray': dasharray,
          });
        var rectBox = span.rect.getBBox();

        var yAdjust = placeReservation(span, rectBox, reservations);

        spanHeights[span.lineIndex] = yAdjust; // this is monotonous due to sort
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
        if (span.drawCurly) {
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
        }
      }); // spans

      // positioning of the chunk
      var chunkBox = chunk.group.getBBox();
      // TODO FIXME why does word wrap glitch?
      if (chunk.lineBreak
          || current.x + chunkBox.width >= canvasWidth - 2 * margin.x) {
        // new row
        var rowBox = row.group.getBBox();
        translate(row, 0, current.y - rowBox.y);
        rows.push(row);
        current.y += rowBox.height + lineSpacing;
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

    // find out how high the arcs have to go
    $.each(data.arcs, function(arcNo, arc) {
      arc.jumpHeight = 0;
      var from = data.spans[arc.origin].lineIndex;
      var to = data.spans[arc.target].lineIndex;
      if (from > to) {
        var tmp = from; from = to; to = tmp;
      }
      for (var i = from + 1; i < to; i++) {
        if (arc.jumpHeight < spanHeights[i]) arc.jumpHeight = spanHeights[i];
      }
    });

    // sort the arcs
    data.arcs.sort(function(a, b) {
      // first write those that have less to jump over
      var tmp = a.jumpHeight - b.jumpHeight;
      if (tmp) return tmp < 0 ? -1 : 1;
      // if equal, then those that span less distance
      tmp = a.dist - b.dist;
      if (tmp) return tmp < 0 ? -1 : 1;
      // if equal, then those where heights of the targets are smaller
      tmp = data.spans[a.origin].height + data.spans[a.target].height -
        data.spans[b.origin].height - data.spans[b.target].height;
      if (tmp) return tmp < 0 ? -1 : 1;
      // if equal, they're just equal.
      return 0;
    });

    // add the arcs
    $.each(data.arcs, function(arcNo, arc) {
      roleClass = 'role_' + arc.type;

      if (!arrows[arc.type]) {
        var arrowId = 'annotator' + id + '_arrow_' + arc.type;
        var arrowhead = svg.marker(defs, arrowId,
          5, 2.5, 5, 5, 'auto',
          {
            markerUnits: 'strokeWidth',
            'class': 'fill_' + arc.type,
          });
        svg.polyline(arrowhead, [[0, 0], [5, 2.5], [0, 5], [0.2, 2.5]]);

        arrows[arc.type] = arrowId;
      }

      var originSpan = data.spans[arc.origin];
      var targetSpan = data.spans[arc.target];
      var originBox = realBBox(originSpan);
      var targetBox = realBBox(targetSpan);
      var leftToRight = originSpan.from + originSpan.to < targetSpan.from + targetSpan.to; // /2 unneeded

      var displacement = originBox.width / 2;
      var sign = leftToRight ? 1 : -1;

      var startX = 
          originBox.x + originBox.width / 2 + sign * displacement;
      var endX =
          targetBox.x + targetBox.width / 2;
      var midX1 = (3 *
        (originBox.x + originBox.width / 2 + sign * displacement) +
        targetBox.x + targetBox.width / 2) / 4;
      var midX2 = (
        originBox.x + originBox.width / 2 + sign * displacement +
        3 * (targetBox.x + targetBox.width / 2)) / 4;
      var pathId = 'annotator' + id + '_path_' + arc.origin + '_' + arc.type;
      var arcHeight = 20 + Math.abs(targetBox.y - originBox.y) / 4;

      var group = svg.group(arcs,
          { 'data-from': arc.origin, 'data-to': arc.target});
      var path = svg.createPath().move(
          startX, originBox.y
        ).curveC(
          midX1, originBox.y - arcHeight,
          midX2, targetBox.y - arcHeight,
          endX, targetBox.y
        );
      svg.path(group, path, {
          markerEnd: 'url(#' + arrows[arc.type] + ')',
          id: leftToRight ? pathId : undefined,
          'class': 'stroke_' + arc.type,
      });
      if (!leftToRight) {
        path = svg.createPath().move(
            endX, targetBox.y
          ).curveC(
            midX2, targetBox.y - arcHeight,
            midX1, originBox.y - arcHeight,
            startX, originBox.y
          );
        svg.path(group, path, {
            stroke: 'none',
            id: pathId,
        });
      }
      var text = svg.text(group, '');
      // svg.textpath(text, '#' + pathId, svg.createText().string(arc.type),
      svg.textpath(text, '#' + pathId, svg.createText().string(arcNo),
        {
          'class': 'fill_' + arc.type,
          startOffset: '50%',
        });
    });
  }

  containerElement.svg({
      onLoad: this.drawInitial,
      settings: {
      /*
          onmouseover: this.variable + ".mouseOver(evt)",
          onmouseout: this.variable + ".mouseOut(evt)",
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
      if (!doc) return;
      $.get(ajaxURL + "&document=" + doc, function(jsonData) {
          drawing = true;
          annotator.renderData(jsonData);
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
