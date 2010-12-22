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
  // settings
  var margin = { x: 2, y: 1 };
  // fine tuning specifically for box text margins
  var boxTextMargin = { x: 0, y: 0.5 };
  var space = 5;
  var boxSpacing = 0;
  var curlyHeight = 6;
  var lineSpacing = 5;
  var arcSpacing = 10;
  var arcSlant = 10;
  var arcStartHeight = 22;
  var arcHorizontalSpacing = 25;
  var dashArray = '3, 3';

  var undefined; // prevents evil "undefined = 17" attacks

  var annotationAbbreviation = {
        "Regulation" : "Reg",
        "Positive_regulation" : "+Reg",
        "Negative_regulation" : "-Reg",
        "Gene_expression" : "Expr",
        "Binding" : "Bind",
        "Transcription" : "Trns",
        "Localization" : "Locl",
        "Protein" : "Prot",
        "Entity" : "Ent",
        "Glycosylation"     : "Glyc",
        "Deglycosylation"   : "Deglyc",
        "Methylation"       : "Meth",
        "Demethylation"     : "Demeth",
        "DNA_methylation"   : "DNA meth",
        "DNA_demethylation" : "DNA demeth",
	"Catalysis"         : "Catal",
	"Biological_process": "Biol.proc",
	"Cellular_physiological_process": "Cell.phys.proc",
	"Protein_family_or_group": "Prot fam/grp",
        };

  var minimalAnnotationAbbreviation = {
        "Protein" : "Pr",
        "Entity"  : "En",
  }

  var arcAbbreviation = {
      "Theme" : "Th",
      "Cause" : "Ca",
      "Site"  : "Si",
      "Equiv" : "Eq",
      "Contextgene" : "CGn",
      "Sidechain" : "SCh",
  };

  if (!Annotator.count) Annotator.count = 0;
  var annId = Annotator.count;
  this.variable = "Annotator[" + annId + "]";
  var annotator = Annotator[Annotator.count] = this;
  Annotator.count++;
  $.browser.chrome = /chrome/.test( navigator.userAgent.toLowerCase() );

  containerElement = $(containerElement);

  var canvasWidth;
  var svg;
  var svgElement;
  var data;

  var highlight;
  var highlightArcs;
  var highlightBoxes;

  // due to silly Chrome bug, I have to make it pay attention
  var forceRedraw = function() {
    if (!$.browser.chrome) return; // not needed
    svgElement.css('margin-bottom', 1);
    setTimeout(function() { svgElement.css('margin-bottom', 0); }, 0);
  }

  var idForSpan = function(span) {
    return 'annotator' + annId + '_span_' + span.id;
  }

  var mouseOver = function(evt) {
    var target = $(evt.target);
    var id;
    if (id = target.attr('data-span-id')) {
      var span = data.spans[id];
      highlight = svg.rect(span.chunk.highlightGroup,
        span.curly.from - 1, span.curly.y - 1,
        span.curly.to + 2 - span.curly.from, span.curly.height + 2,
        { 'class': 'span_default span_' + span.type });
      highlightArcs = target.closest('svg').find('.arcs').
          find('g[data-from="' + id + '"], g[data-to="' + id + '"]').
          addClass('highlight');
      /*
      // TODO: Find out why incoming and outgoing are structure-shared
      // >.<
      var boxes = ['#' + idForSpan(span)];
      boxes.push('foo');
      $.each(span.incoming, function(arcNo, arc) {
        boxes.push('#' + idForSpan(data.spans[arc.origin]));
      });
      boxes.push('foo');
      $.each(span.outgoing, function(arcNo, arc) {
        boxes.push('#' + idForSpan(data.spans[arc.target]));
      });
      highlightBoxes = $(boxes.join(', '))
        .addClass('highlight');
      */
      forceRedraw();
    }
  };

  var mouseOut = function(evt) {
    if (highlight) {
      svg.remove(highlight);
      highlight = undefined;
    }
    if (highlightArcs) {
      highlightArcs.removeClass('highlight');
      highlightArcs = undefined;
    }
    if (highlightBoxes) {
      highlightBoxes.removeClass('highlight');
      highlightBoxes = undefined;
    }
    forceRedraw();
  };

  var click = function(evt) {
    // DEBUG
    var target = $(evt.target);
    var id;
    if (id = target.attr('data-span-id')) {
      var span = data.spans[id];
      console.log(span.id, span); // DEBUG
    }
  }

  this.drawInitial = function(_svg) {
    svg = _svg;
    svgElement = $(svg._svg);
    if (onStart) onStart.call(annotator);

    containerElement.mouseover(mouseOver);
    containerElement.mouseout(mouseOut);
    containerElement.click(click);
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
  var EventDesc = function(id, triggerId, roles, equiv) {
    this.id = id;
    this.triggerId = triggerId;
    var roleList = this.roles = [];
    $.each(roles, function(roleNo, role) {
      roleList.push({ type: role[0], targetId: role[1] });
    });
    if (equiv) this.equiv = true;
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
    $.each(data.equivs, function(equivNo, equiv) {
      var eventDesc = data.eventDescs[equiv[0]] =
          new EventDesc(equiv[1], equiv[1], [['Equiv', equiv[2]]], true);
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
        if (!target) {
          console.error('Error: "' + role.targetId + '" not found in ' + data.document);
        }
        var there = target.chunk.index;
        var dist = Math.abs(here - there);
        var arc = {
          origin: eventDesc.id,
          target: role.targetId,
          dist: dist,
          type: role.type,
          jumpHeight: 0,
        };
        if (eventDesc.equiv) arc.equiv = true;
        origin.totalDist += dist;
        origin.numArcs++;
        target.totalDist += dist;
        target.numArcs++;
        data.arcs.push(arc);
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
        // earlier-starting ones go first
        tmp = a.from - b.from;
        if (tmp) {
          return tmp < 0 ? -1 : 1;
        }
        // compare the span widths,
        // put wider on bottom so they don't mess with arcs
        var ad = a.to - a.from;
        var bd = b.to - b.from;
        tmp = ad - bd;
        if (tmp) {
          return tmp < 0 ? 1 : -1;
        }
        // longer arc distances go last
        var tmp = a.avgDist - b.avgDist;
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
      for (var resNo = 0, resLen = reservations.length; resNo < resLen; resNo++) {
        var reservation = reservations[resNo];
        var line = reservation.ranges;
        height = reservation.height;
        var overlap = false;
        $.each(line, function(slotNo, slot) {
          var slot = line[slotNo];
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
      }
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
    this.background = svg.group(this.group);
    this.chunks = [];
  }

  var rowBBox = function(span) {
    var box = span.rect.getBBox();
    var chunkTranslation = span.chunk.translation;
    box.x += chunkTranslation.x;
    box.y += chunkTranslation.y;
    return box;
  }

  this.renderData = function(_data) {
    setData(_data);
    svg.clear(true);
    if (!data || data.length == 0) return;
    canvasWidth = $(containerElement).width();
    $(svg).attr('width', canvasWidth);
    
    var current = { x: margin.x, y: margin.y };
    var rows = [];
    var spanHeights = [];
    var row = new Row();
    row.index = 0;
    var rowIndex = 0;
    var textHeight;
    var reservations;
    var lastBoxChunkIndex = -1;

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
      var chunkIndexFrom, chunkIndexTo;
      var minArcDist;
      var lastArcBorder = 0;
      var hasLeftArcs, hasRightArcs, hasInternalArcs;

      $.each(chunk.spans, function(spanNo, span) {
        span.chunk = chunk;
        span.group = svg.group(chunk.group, {
          'class': 'span',
          id: idForSpan(span),
        });

        // measure the text span
        var measureText = svg.text(chunk.group, 0, 0,
          chunk.text.substr(0, span.from - chunk.from));
        var xFrom = measureText.getBBox().width;
        if (xFrom < 0) xFrom = 0;
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

	// Two modes of abbreviation applied if needed
	// and abbreviation defined.
	var abbrevText = span.type;
	if(span.to-span.from < abbrevText.length) {
	    abbrevText = annotationAbbreviation[span.type] || abbrevText;
	}
	if(span.to-span.from < abbrevText.length) {
	    abbrevText = minimalAnnotationAbbreviation[span.type] || abbrevText;
	}

        var spanText = svg.text(span.group, x, y, abbrevText);
        var spanBox = spanText.getBBox();

	// text margin fine-tuning
	spanBox.y      += boxTextMargin.y;
	spanBox.height -= 2*boxTextMargin.y;

        svg.remove(spanText);
        span.rect = svg.rect(span.group,
          spanBox.x - margin.x,
          spanBox.y - margin.y,
          spanBox.width + 2 * margin.x,
          spanBox.height + 2 * margin.y, {
            'class': 'span_' + span.type + ' span_default',
            rx: margin.x,
            ry: margin.y,
            'data-span-id': span.id,
            'strokeDashArray': span.Speculation ? dashArray : undefined,
          });
        var rectBox = span.rect.getBBox();

        if (chunkIndexFrom == undefined || chunkIndexFrom > span.lineIndex)
          chunkIndexFrom = span.lineIndex;
        if (chunkIndexTo == undefined || chunkIndexTo < span.lineIndex)
          chunkIndexTo = span.lineIndex;
        var yAdjust = placeReservation(span, rectBox, reservations);
        // this is monotonous due to sort:
        span.height = yAdjust + spanBox.height + 3 * margin.y + curlyHeight + arcSpacing;
        spanHeights[span.lineIndex * 2] = span.height;
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

        // find the last arc backwards
        $.each(span.incoming, function(arcId, arc) {
          var origin = data.spans[arc.origin].chunk;
          if (chunk.index == origin.index) {
            hasInternalArcs = true;
          }
          if (origin.row) {
            hasLeftArcs = true;
            if (origin.row.index == rowIndex) {
              // same row, but before this
              var border = origin.translation.x + origin.box.x + origin.box.width;
              if (border > lastArcBorder) lastArcBorder = border;
            }
          } else {
            hasRightArcs = true;
          }
        });
        $.each(span.outgoing, function(arcId, arc) {
          var target = data.spans[arc.target].chunk;
          if (target.row) {
            hasLeftArcs = true;
            if (target.row.index == rowIndex) {
              // same row, but before this
              var border = target.translation.x + target.box.x + target.box.width;
              if (border > lastArcBorder) lastArcBorder = border;
            }
          } else {
            hasRightArcs = true;
          }
        });
      }); // spans

      var len = chunkIndexTo * 2;
      for (var i = chunkIndexFrom * 2 + 1; i < len; i++)
        spanHeights[i] = Math.max(spanHeights[i - 1], spanHeights[i + 1]);

      // positioning of the chunk
      var spacing;
      var chunkBox = chunk.box = chunk.group.getBBox();
      if (hasLeftArcs) {
        var spacing = arcHorizontalSpacing - (current.x - lastArcBorder);
        // arc too small?
        if (spacing > 0) current.x += spacing;
      }
      var rightBorderForArcs = hasRightArcs ? arcHorizontalSpacing : (hasInternalArcs ? arcSlant : 0);

      if (chunk.lineBreak ||
          current.x + chunkBox.width + rightBorderForArcs >= canvasWidth - 2 * margin.x) {
        row.arcs = svg.group(row.group, { 'class': 'arcs' });
        // new row
        rows.push(row);
        current.x = margin.x + (hasLeftArcs ? arcHorizontalSpacing : (hasInternalArcs ? arcSlant : 0));
        svg.remove(chunk.group);
        row = new Row();
        lastBoxChunkIndex = chunk.index - 1;
        row.index = ++rowIndex;
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

      if (spacing > 0) {
        // if we added a gap, center the intervening elements
        spacing /= 2;
        while (++lastBoxChunkIndex < chunk.index) {
          var movedChunk = data.chunks[lastBoxChunkIndex];
          translate(movedChunk, movedChunk.translation.x + spacing, 0);
        }
      }
      if (chunk.spans.length) lastBoxChunkIndex = chunk.index;

      row.chunks.push(chunk);
      chunk.row = row;
      translate(chunk, current.x - chunkBox.x, 0);

      current.x += chunkBox.width + space;
    }); // chunks

    // finish the last row
    row.arcs = svg.group(row.group, { 'class': 'arcs' });
    rows.push(row);

    var defs = svg.defs();
    var arrows = {};

    var len = spanHeights.length;
    for (var i = 0; i < len; i++) {
      if (!spanHeights[i] || spanHeights[i] < arcStartHeight) spanHeights[i] = arcStartHeight;
    }

    // find out how high the arcs have to go
    $.each(data.arcs, function(arcNo, arc) {
      arc.jumpHeight = 0;
      var from = data.spans[arc.origin].lineIndex;
      var to = data.spans[arc.target].lineIndex;
      if (from > to) {
        var tmp = from; from = to; to = tmp;
      }
      for (var i = from + 1; i < to; i++) {
        if (arc.jumpHeight < spanHeights[i * 2]) arc.jumpHeight = spanHeights[i * 2];
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
      // if equal, then those with the lower origin
      tmp = data.spans[a.origin].height - data.spans[b.origin].height;
      if (tmp) return tmp < 0 ? -1 : 1;
      // if equal, they're just equal.
      return 0;
    });

    // add the arcs
    $.each(data.arcs, function(arcNo, arc) {
      roleClass = 'role_' + arc.type;

      if (!arrows[arc.type]) {
        var arrowId = 'annotator' + annId + '_arrow_' + arc.type;
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

      var leftToRight = originSpan.lineIndex < targetSpan.lineIndex;
      var left, right;
      if (leftToRight) {
        left = originSpan;
        right = targetSpan;
      } else {
        left = targetSpan;
        right = originSpan;
      }
      var leftBox = rowBBox(left);
      var rightBox = rowBBox(right);
      var leftRow = left.chunk.row.index;
      var rightRow = right.chunk.row.index;

      var fromIndex = left.lineIndex;
      var toIndex = right.lineIndex;

      // find the next height
      var height = 0;
      var fromIndex2 = fromIndex * 2;
      var toIndex2 = toIndex * 2;
      if (left.chunk.index != right.chunk.index) {
        fromIndex2++;
        toIndex2--;
      }
      for (var i = fromIndex2; i <= toIndex2; i++) {
        if (spanHeights[i] > height) height = spanHeights[i];
      }
      height += arcSpacing;
      var leftSlantBound, rightSlantBound;
      for (var i = fromIndex2; i <= toIndex2; i++) {
        if (spanHeights[i] < height) spanHeights[i] = height;
      }

      var chunkReverse = false;
      if (originSpan.chunk.index == targetSpan.chunk.index) {
        chunkReverse =
          leftBox.x + leftBox.width / 2 < rightBox.x + rightBox.width / 2;
      }
      var chunkReverseSign = chunkReverse ? -1 : 1;

      for (var rowIndex = leftRow; rowIndex <= rightRow; rowIndex++) {
        var row = rows[rowIndex];
        var arcGroup = svg.group(row.arcs,
            { 'data-from': arc.origin, 'data-to': arc.target });
        var from, to;
        
        if (rowIndex == leftRow) {
          from = leftBox.x + (chunkReverse ? 0 : leftBox.width);
        } else {
          from = 0;
        }

        if (rowIndex == rightRow) {
          to = rightBox.x + (chunkReverse ? rightBox.width : 0);
        } else {
          to = canvasWidth - 2 * margin.y;
        }

        var abbrevText = arcAbbreviation[arc.type] || arc.type;
        if((to-from)/15 > arc.type.length || !abbrevText) {
          // no need to (or cannot) abbreviate
          // TODO cleaner heuristic
          abbrevText = arc.type;
        }
        var text = svg.text(arcGroup, (from + to) / 2, -height, abbrevText, {
            'class': 'fill_' + arc.type,
        });
        var textBox = text.getBBox();
        var textStart = textBox.x - margin.x;
        var textEnd = textStart + textBox.width + 2 * margin.x;
        if (from > to) {
          var tmp = textStart; textStart = textEnd; textEnd = tmp;
        }

        var path;
        path = svg.createPath().move(textStart, -height);
        if (rowIndex == leftRow) {
          path.line(from + chunkReverseSign * arcSlant, -height).
            line(from, leftBox.y + (leftToRight || arc.equiv ? leftBox.height / 2 : margin.y));
        } else {
          path.line(from, -height);
        }
        svg.path(arcGroup, path, {
            markerEnd: leftToRight || arc.equiv ? undefined : ('url(#' + arrows[arc.type] + ')'),
            'class': 'stroke_' + arc.type,
            'strokeDashArray': arc.equiv ? dashArray : undefined,
        });
        path = svg.createPath().move(textEnd, -height);
        if (rowIndex == rightRow) {
          path.line(to - chunkReverseSign * arcSlant, -height).
            line(to, rightBox.y + (leftToRight && !arc.equiv ? margin.y : rightBox.height / 2));
        } else {
          path.line(to, -height);
        }
        svg.path(arcGroup, path, {
            markerEnd: leftToRight && !arc.equiv ? 'url(#' + arrows[arc.type] + ')' : undefined,
            'class': 'stroke_' + arc.type,
            'strokeDashArray': arc.equiv ? dashArray : undefined,
        });
      } // arc rows
    }); // arcs

    var y = margin.y;
    $.each(rows, function(rowId, row) {
      var rowBox = row.group.getBBox();
      svg.rect(row.background,
        0, rowBox.y, canvasWidth, rowBox.height, {
        'class': 'background' + (rowId % 2),
      });
      y += rowBox.height;
      translate(row, 0, y);
      y += margin.y;
    });
    y += margin.y;

    // resize the SVG
    $(svg._svg).attr('height', y).css('height', y);
    $(containerElement).attr('height', y).css('height', y);
  }

  this.getSVG = function() {
    return containerElement.html();
  };

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
  var ajaxBase = base + 'ajax.cgi';
  var ajaxURL = ajaxBase + "?directory=" + directory;
  var docListReceived = false;

  $.get(ajaxURL, function(data) {
    docListReceived = true;
    $('#document_select').html(data).val(doc);
  });

  var annotator = new Annotator('#svg', function() {
    var annotator = this;

    var lastHash = null;
    var directoryAndDoc;
    var drawing = false;
    var savePassword;
    var updateState = function() {
      if (drawing || lastHash == window.location.hash) return;
      lastHash = window.location.hash;
      var parts = lastHash.substr(1).split('/');
      directory = parts[0];
      var _doc = doc = parts[1];
      if (_doc == 'save' && (savePassword = parts[2])) return;
      $('#document_select').val(_doc);

      $('#document_name').text(directoryAndDoc);
      if (!_doc) return;
      $.get(ajaxURL + "&document=" + _doc, function(jsonData) {
          drawing = true;
          jsonData.document = _doc;
          annotator.renderData(jsonData);
          drawing = false;
      });
    };

    var renderDocument = function(_doc) {
      doc = _doc;
      directoryAndDoc = directory + (doc ? '/' + doc : '');
      window.location.hash = '#' + directoryAndDoc;
      updateState();
    };

    var renderSelected = function(evt) {
      doc = $('#document_select').val();
      renderDocument(doc);
      return false;
    };

    var renderToDiskAndSelectNext = function() {
      var _doc = doc;
      if (!savePassword) return;
      renderSelected();
      // see if converting to string helps?
      var svgMarkup = '' + annotator.getSVG();
      $.ajax({
        type: 'POST',
        url: ajaxBase,
        data: {
          directory: directory,
          document: _doc,
          save: savePassword,
          svg: svgMarkup,
        },
        error: function(req, textStatus, errorThrown) {
          console.error(_doc, textStatus, errorThrown);
          if (savePassword) {
            savePassword = undefined;
            alert('Error occured.\nSVG dump aborted.');
          }
        },
        success: function(data) {
            // silently ignore
        }
      });
      var select = $('#document_select')[0];
      select.selectedIndex = select.selectedIndex + 1;
      if (select.selectedIndex != -1) {
        setTimeout(renderToDiskAndSelectNext, 0);
      } else {
        console.log('done');
      }
    };

    var renderAllToDisk = function() {
      if (docListReceived) {
        $('#document_select')[0].selectedIndex = 1;
        renderToDiskAndSelectNext();
      } else {
        setTimeout(renderAllToDisk, 100);
      }
    };

    $('#document_form').
        submit(renderSelected).
        children().
        removeAttr('disabled');

    $('#document_select').
        change(renderSelected);

    directoryAndDoc = directory + (doc ? '/' + doc : '');
    updateState(doc);
    if (savePassword) {
      renderAllToDisk();
    } else {
      setInterval(updateState, 200); // TODO okay?
    }
  });

  $(window).resize(function(evt) {
    annotator.renderData();
  });
});
