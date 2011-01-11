// (C) Goran Topic amadan@mad.scientist.com
//
// All rights reserved
// Do not modify or redistribute without an explicit permission
//
// This temporary licence will probably be relaxed in near future
// Thank you for your cooperation.

// make JS debugger-friendly
if (typeof(console) === 'undefined') {
  var console = {};
  console.log = console.error = console.info = console.debug =
      console.warn = console.trace = console.dir = console.dirxml =
      console.group = console.groupEnd = console.time =
      console.timeEnd = console.assert = console.profile =
      function() {};
}


var displayMessage;

// SVG Annotation tool
var Annotator = function(containerElement, onStart) {
  // settings
  var margin = { x: 2, y: 1 };
  // fine tuning specifically for box text margins
  var boxTextMargin = { x: 0, y: 0 };
  var space = 5;
  var boxSpacing = 1;
  var curlyHeight = 6;
  var lineSpacing = 5;
  var arcSpacing = 10;
  var arcSlant = 10;
  var arcStartHeight = 30; //22;
  var arcHorizontalSpacing = 25;
  var dashArray = '3,3';
  var rowSpacing = 5;
  var user;
  var password;

  var undefined; // prevents evil "undefined = 17" attacks

  var annotationAbbreviations = {
      "gene-or-gene-product" : [ "GGP" ],

      "Protein" : [ "Pro", "Pr", "P" ],
      "Entity"  : [ "Ent", "En", "E" ],

      "Multicellular_organism_natural" : [ "M-C Organism", "MCOrg" ],
      "Organism"             : [ "Org" ],
      "Chemical"             : [ "Chem" ],
      "Two-component-system" : [ "2-comp-sys", "2CS" ],
      "Regulon-operon"       : [ "Reg/op" ],

      "Protein_catabolism"   : [ "Catabolism", "Catab" ],
      "Gene_expression"      : [ "Expression", "Expr" ],
      "Binding"              : [ "Bind" ],
      "Transcription"        : [ "Trns" ],
      "Localization"         : [ "Locl" ],
      "Regulation"           : [ "Reg" ],
      "Positive_regulation"  : [ "+Regulation", "+Reg" ],
      "Negative_regulation"  : [ "-Regulation", "-Reg" ],
      "Phosphorylation"      : [ "Phos" ],
      "Dephosphorylation"    : [ "-Phos" ],
      "Acetylation"          : [ "Acet" ],
      "Deacetylation"        : [ "-Acet" ],
      "Hydroxylation"        : [ "Hydr" ],
      "Dehydroxylation"      : [ "-Hydr" ],
      "Glycosylation"        : [ "Glyc" ],
      "Deglycosylation"      : [ "-Glyc" ],
      "Methylation"          : [ "Meth" ],
      "Demethylation"        : [ "-Meth" ],
      "Ubiquitination"       : [ "Ubiq" ],
      "Deubiquitination"     : [ "-Ubiq" ],
      "DNA_methylation"      : [ "DNA meth" ],
      "DNA_demethylation"    : [ "DNA -meth" ],
      "Catalysis"            : [ "Catal" ],
      "Biological_process"   : [ "Biol proc" ],
      "Cellular_physiological_process": [ "Cell phys proc" ],
      "Protein_molecule": [ "Prot mol" ],
      "Protein_family_or_group": [ "Prot f/g" ],
      "DNA_domain_or_region": [ "DNA d/r" ],

  };

  var arcAbbreviation = {
      "Theme" : "Th",
      "Theme1": "Th1",
      "Theme2": "Th2",
      "Theme3": "Th3",
      "Theme4": "Th4",
      "Cause" : "Ca",
      "Site"  : "Si",
      "Site1" : "Si1",
      "Site2" : "Si2",
      "Site3" : "Si3",
      "Site4" : "Si4",
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
  var svgPosition;
  var data;

  var highlight;
  var highlightArcs;
  var arcDragOrigin;
  var arcDragArc;
  var arcDragOriginBox;
  var arcDragOriginGroup;
  var dragArrowId;
  var highlightGroup;
  var curlyY;

  // due to silly Chrome bug, I have to make it pay attention
  var forceRedraw = function() {
    if (!$.browser.chrome) return; // not needed
    svgElement.css('margin-bottom', 1);
    setTimeout(function() { svgElement.css('margin-bottom', 0); }, 0);
  }

  var makeId = function(name) {
    return 'annotator' + annId + '_' + name;
  }

  var mouseOver = function(evt) {
    var target = $(evt.target);
    var id;
    if (id = target.attr('data-span-id')) {
      var span = data.spans[id];
      highlight = svg.rect(highlightGroup,
        span.chunk.textX + span.curly.from - 1, span.chunk.row.textY + curlyY - 1,
        span.curly.to + 2 - span.curly.from, span.curly.height + 2,
        { 'class': 'span_default span_' + span.type });
      if (arcDragOrigin) {
        target.parent().addClass('highlight');
      } else {
        highlightArcs = target.closest('svg').find('.arcs').
            find('g[data-from="' + id + '"], g[data-to="' + id + '"]').
            addClass('highlight');
      }
      forceRedraw();
    } else if (!arcDragOrigin && (id = target.attr('data-arc-role'))) {
      var originSpanId = target.attr('data-arc-origin');
      var targetSpanId = target.attr('data-arc-target');
      highlightArcs = target.closest('svg').find('.arcs').
          find('g[data-from="' + originSpanId + '"][data-to="' + targetSpanId + '"]').
          addClass('highlight');
    }
  };

  var mouseOut = function(evt) {
    var target = $(evt.target);
    if (arcDragOrigin && arcDragOrigin != target.attr('data-span-id')) {
      target.parent().removeClass('highlight');
    }
    if (highlight) {
      svg.remove(highlight);
      highlight = undefined;
    }
    if (highlightArcs) {
      highlightArcs.removeClass('highlight');
      highlightArcs = undefined;
    }
    forceRedraw();
  };

  this.deleteSpan = function(evt) {
    $('#span_form').css('display', 'none');
    annotator.ajaxOptions.action = 'unspan';
    annotator.postChangesAndReload();
  };

  this.deleteArc = function(evt) {
    $('#arc_form').css('display', 'none');
    annotator.ajaxOptions.action = 'unarc';
    annotator.postChangesAndReload();
  };

  var dblClick = function(evt) {
    if (!user) return;
    var target = $(evt.target);
    var id;
    // do we edit an arc?
    if (id = target.attr('data-arc-role')) {
      window.getSelection().removeAllRanges();
      var originSpanId = target.attr('data-arc-origin');
      var targetSpanId = target.attr('data-arc-target');
      var type = target.attr('data-arc-role');
      var originSpan = data.spans[originSpanId];
      var targetSpan = data.spans[targetSpanId];
      annotator.ajaxOptions = {
        action: 'arc',
        origin: originSpanId,
        target: targetSpanId,
      };
      $('#arc_origin').text(originSpan.type+' ("'+data.text.substring(originSpan.from, originSpan.to)+'")');
      $('#arc_target').text(targetSpan.type+' ("'+data.text.substring(targetSpan.from, targetSpan.to)+'")');
      $('#del_arc_button').css('display', 'inline');
      annotator.fillArcTypesAndDisplayForm(originSpan.type, targetSpan.type, type);
      
    // if not, then do we edit a span?
    } else if (id = target.attr('data-span-id')) {
      window.getSelection().removeAllRanges();
      var span = data.spans[id];
      annotator.ajaxOptions = {
        action: 'span',
        id: id,
      };
      $('#span_selected').text(data.text.substring(span.from, span.to));
      $('#del_span_button').css('display', 'inline');
      $('#span_form').css('display', 'block');
      var el = $('#span_' + span.type);
      if (el.length) {
        el[0].checked = true;
      } else {
        $('#span_free_text').val(span.type);
        $('#span_free_entry')[0].checked = true;
      }
    }
  };

  var mouseDown = function(evt) {
    if (!user) return;
    var target = $(evt.target);
    var id;
    // is it arc drag start?
    if (id = target.attr('data-span-id')) {
      svgPosition = svgElement.offset();
      arcDragOrigin = id;
      arcDragArc = svg.path(svg.createPath(), {
        markerEnd: 'url(#' + dragArrowId + ')',
        'class': 'drag_stroke',
        fill: 'none',
      });
      arcDragOriginGroup = $(data.spans[arcDragOrigin].group);
      arcDragOriginGroup.addClass('highlight');
      arcDragOriginBox = realBBox(data.spans[arcDragOrigin]);
      arcDragOriginBox.center = arcDragOriginBox.x + arcDragOriginBox.width / 2;
      return false;
    }
  };

  var mouseMove = function(evt) {
    if (arcDragOrigin) {
      var mx = evt.pageX - svgPosition.left;
      var my = evt.pageY - svgPosition.top + 5; // TODO FIXME why +5?!?
      var y = Math.min(arcDragOriginBox.y, my) - 50;
      var dx = (arcDragOriginBox.center - mx) / 4;
      var path = svg.createPath().
        move(arcDragOriginBox.center, arcDragOriginBox.y).
        curveC(arcDragOriginBox.center - dx, y,
            mx + dx, y,
            mx, my);
      arcDragArc.setAttribute('d', path.path());
    }
  }

  var mouseUp = function(evt) {
    if (!user) return;
    var target = $(evt.target);
    // is it arc drag end?
    if (arcDragOrigin) {
      arcDragOriginGroup.removeClass('highlight');
      target.parent().removeClass('highlight');
      if ((id = target.attr('data-span-id')) && arcDragOrigin != id) {
        var originSpan = data.spans[arcDragOrigin];
        var targetSpan = data.spans[id];
        annotator.ajaxOptions = {
          action: 'arc',
          origin: originSpan.id,
          target: targetSpan.id,
        };
        $('#arc_origin').text(originSpan.type+' ("'+data.text.substring(originSpan.from, originSpan.to)+'")');
	$('#arc_target').text(targetSpan.type+' ("'+data.text.substring(targetSpan.from, targetSpan.to)+'")');
        $('#del_arc_button').css('display', 'none');
        annotator.fillArcTypesAndDisplayForm(originSpan.type, targetSpan.type);
      }
      svg.remove(arcDragArc);
      arcDragOrigin = undefined;
    } else {
      // if not, then is it span selection?
      var sel = window.getSelection();
      var chunkIndexFrom = sel.anchorNode && $(sel.anchorNode.parentNode).attr('data-chunk-id');
      var chunkIndexTo = sel.focusNode && $(sel.focusNode.parentNode).attr('data-chunk-id');
      if (chunkIndexFrom != undefined && chunkIndexTo != undefined) {
        var chunkFrom = data.chunks[chunkIndexFrom];
        var chunkTo = data.chunks[chunkIndexTo];
        var selectedFrom = chunkFrom.from + sel.anchorOffset;
        var selectedTo = chunkTo.from + sel.focusOffset;
        window.getSelection().removeAllRanges();
        if (selectedFrom == selectedTo) return; // simple click (zero-width span)
        if (selectedFrom > selectedTo) {
          var tmp = selectedFrom; selectedFrom = selectedTo; selectedTo = tmp;
        }
        annotator.ajaxOptions = {
          action: 'span',
          from: selectedFrom,
          to: selectedTo,
        };
        $('#span_selected').text(data.text.substring(selectedFrom, selectedTo));
        $('#del_span_button').css('display', 'none');
        $('#span_form').css('display', 'block');
      }
    }
  };

  this.drawInitial = function(_svg) {
    svg = _svg;
    svgElement = $(svg._svg);
    if (onStart) onStart.call(annotator);

    containerElement.mouseover(mouseOver);
    containerElement.mouseout(mouseOut);
    containerElement.mousemove(mouseMove);
    containerElement.dblclick(dblClick);
    containerElement.mouseup(mouseUp);
    containerElement.mousedown(mouseDown);
  }

  var Span = function(id, type, from, to, generalType) {
    this.id = id;
    this.type = type;
    this.from = parseInt(from);
    this.to = parseInt(to);
    this.outgoing = [];
    this.incoming = [];
    this.totalDist = 0;
    this.numArcs = 0;
    this.generalType = generalType;
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
          new Span(entity[0], entity[1], entity[2], entity[3], 'entity');
      data.spans[entity[0]] = span;
    });
    var triggerHash = {};
    $.each(data.triggers, function(triggerNo, trigger) {
      triggerHash[trigger[0]] =
          new Span(trigger[0], trigger[1], trigger[2], trigger[3], 'trigger');
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
      var equivSpans = equiv.slice(2);
      equivSpans.sort(function(a, b) {
        var aSpan = data.spans[a];
        var bSpan = data.spans[b];
        var tmp = aSpan.from + aSpan.to - bSpan.from - bSpan.to;
        if (tmp) {
          return tmp < 0 ? -1 : 1;
        }
        return 0;
      });
      var len = equivSpans.length;
      for (var i = 1; i < len; i++) {
        var eventDesc = data.eventDescs[equiv[0] + '*' + i] =
            new EventDesc(equivSpans[i - 1], equivSpans[i - 1], [[equiv[1], equivSpans[i]]], true);
      }
    });

    // find chunk breaks
    var breaks = [[-1, false]];
    var pos = -1;
    while ((pos = data.text.indexOf('\n', pos + 1)) != -1) {
      breaks.push([pos, true, true]);
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
            newSentence: breaks[breakNo][2],
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
          throw "BadDocumentError";
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
      }); // roles
    }); // eventDescs

    var sortedSpans = [];
    // sort spans in chunks for drawing purposes
    var lastSpan = null;
    $.each(data.chunks, function(chunkNo, chunk) {
      $.each(chunk.spans, function(spanNo, span) {
        sortedSpans.push(span);
        span.avgDist = span.totalDist / span.numArcs;
      });
      chunk.spans.sort(function(a, b) {
        // longer arc distances go last
        var tmp = a.avgDist - b.avgDist;
        if (tmp) {
          return tmp < 0 ? -1 : 1;
        }
        // spans with more arcs go last
        var tmp = a.numArcs - b.numArcs;
        if (tmp) {
          return tmp < 0 ? -1 : 1;
        }
        // compare the span widths,
        // put wider on bottom so they don't mess with arcs, or shorter
	// on bottom if there are no arcs.
        var ad = a.to - a.from;
        var bd = b.to - b.from;
        tmp = ad - bd;
	if(a.numArcs == 0 && b.numArcs == 0) {
	    tmp = -tmp;
	} 
        if (tmp) {
          return tmp < 0 ? 1 : -1;
        }
        return 0;
      }); // spans
      // number the spans so we can check for heights later
      $.each(chunk.spans, function(i, span) {
        if (!lastSpan || (lastSpan.from != span.from || lastSpan.to != span.to)) {
          span.drawCurly = true;
        }
        lastSpan = span;
      }); // spans
    }); // chunks

    // sort the spans for linear order
    sortedSpans.sort(function(a, b) {
      var tmp = a.from + a.to - b.from - b.to;
      if (tmp) {
        return tmp < 0 ? -1 : 1;
      }
      return 0;
    });
    var realSpanNo = -1;
    var lastSpan;
    $.each(sortedSpans, function(spanNo, span) {
      if (!lastSpan || span.from != lastSpan.from || span.to != lastSpan.to) realSpanNo++;
      span.lineIndex = realSpanNo;
      if (span.chunk.firstSpanIndex == undefined) span.chunk.firstSpanIndex = realSpanNo;
      span.chunk.lastSpanIndex = realSpanNo;
      lastSpan = span;
    });
  }

  var placeReservation = function(span, box, reservations) {
    var newSlot = {
      from: box.x,
      to: box.x + box.width,
      span: span,
      height: box.height + (span.drawCurly ? curlyHeight : 0),
    };
    // TODO look at this, and remove if ugly
    // example where it matters: the degenerate case of
    // http://www-tsujii.is.s.u-tokyo.ac.jp/GENIA/SharedTask/goran/visual/annotator.xhtml#miwa-genia-dev/9794389
    // (again, it would be solved by individual box reservations instead
    // of row-based)
    
    // overlapping curly check: TODO delete or uncomment
    /*
    if (span.drawCurly) {
      if (span.curly.from < newSlot.from) newSlot.from = span.curly.from;
      if (span.curly.to > newSlot.to) newSlot.to = span.curly.to;
    }
    */
    var height = 0;
    if (reservations.length) {
      for (var resNo = 0, resLen = reservations.length; resNo < resLen; resNo++) {
        var reservation = reservations[resNo];
        var line = reservation.ranges;
        height = reservation.height;
        var overlap = false;
        $.each(line, function(slotNo, slot) {
          var slot = line[slotNo];
          // with the curly change above, we can live with sharing
          // borders
          if (slot.from < newSlot.to && newSlot.from < slot.to) {
            overlap = true;
            return false;
          }
        });
        if (!overlap) {
          if (!reservation.curly && span.drawCurly) {
            // TODO: need to push up the boxes drawn so far
            // (rare glitch)
            // it would be prettier to track individual boxes (and not
            // rows) but the cases when it matters are rare, and not
            // worth the bother so far
            reservation.height += curlyHeight;
          }
          line.push(newSlot);
          return reservation.height;
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
    this.hasAnnotations = 0;
  }

  var rowBBox = function(span) {
    var box = span.rect.getBBox();
    var chunkTranslation = span.chunk.translation;
    box.x += chunkTranslation.x;
    box.y += chunkTranslation.y;
    return box;
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
    svg.clear(true);
    var defs = svg.defs();
    if (!data || data.length == 0) return;
    canvasWidth = this.forceWidth || $(containerElement).width();
    var commentName = data.document.replace('--', '-\\-');
    svgElement.
        attr('width', canvasWidth).
        append('<!-- document: ' + commentName + ' -->');
    
    // set up the text element, find out font height
    var backgroundGroup = svg.group({ 'class': 'background' });
    highlightGroup = svg.group({ 'class': 'highlight' });
    var textGroup = svg.group({ 'class': 'text' });
    var textSpans = svg.createText();
    $.each(data.chunks, function(chunkNo, chunk) {
      textSpans.span(chunk.text, {
          id: makeId('chunk' + chunk.index),
          'data-chunk-id': chunk.index,
      });
    });
    var text = svg.text(textGroup, 0, 0, textSpans, {'class': 'text'});
    var textHeight = text.getBBox().height;

    var current = { x: margin.x, y: margin.y }; // TODO: we don't need some of this?
    var rows = [];
    var spanHeights = [];
    var row = new Row();
    var sentenceToggle = 0;
    row.backgroundIndex = sentenceToggle;
    row.index = 0;
    var rowIndex = 0;
    var reservations;
    var lastBoxChunkIndex = -1;


    $.each(data.chunks, function(chunkNo, chunk) {
      reservations = new Array();
      chunk.group = svg.group(row.group);

      var y = 0;
      var minArcDist;
      var lastArcBorder = 0;
      var hasLeftArcs, hasRightArcs, hasInternalArcs;
      var hasAnnotations;

      $.each(chunk.spans, function(spanNo, span) {
        span.chunk = chunk;
        span.group = svg.group(chunk.group, {
          'class': 'span',
          id: makeId('span_' + span.id),
        });

        // measure the text span
        var measureText = svg.text(textGroup, 0, 0,
          chunk.text.substr(0, span.from - chunk.from));
        var xFrom = measureText.getBBox().width;
        if (xFrom < 0) xFrom = 0;
        svg.remove(measureText);
        measureText = svg.text(textGroup, 0, 0,
          chunk.text.substr(0, span.to - chunk.from));
        var measureBox = measureText.getBBox();
        if (!y) y = -textHeight - curlyHeight;
        var xTo = measureBox.width;
        span.curly = {
          from: xFrom,
          to: xTo,
          height: measureBox.height,
        };
        curlyY = measureBox.y,
        svg.remove(measureText);
        var x = (xFrom + xTo) / 2;

	// Two modes of abbreviation applied if needed
	// and abbreviation defined.
	var abbrevText = span.type;

	var abbrevIdx  = 0;
	var spanLength = span.to - span.from;
	while(abbrevText.length > spanLength/0.8 &&
	      annotationAbbreviations[span.type] &&
	      annotationAbbreviations[span.type][abbrevIdx]) {
	    abbrevText = annotationAbbreviations[span.type][abbrevIdx];
	    abbrevIdx++;
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
        hasAnnotations = true;
      }); // spans

      if (chunk.newSentence) sentenceToggle = 1 - sentenceToggle;

      chunk.tspan = $('#' + makeId('chunk' + chunk.index));

      // positioning of the chunk
      var spacing;
      var chunkBox = chunk.box = chunk.group.getBBox();
      var measureText = svg.text(textGroup, 0, 0, chunk.text);
      var textBox = measureText.getBBox();
      svg.remove(measureText);
      if (!chunkBox) { // older Firefox bug
        chunkBox = { x: 0, y: 0, height: 0, width: 0 };
      }
      chunkBox.height += textBox.height;
      var boxX = -Math.min(chunkBox.x, textBox.x);
      var boxWidth =
          Math.max(textBox.x + textBox.width, chunkBox.x + chunkBox.width) -
          Math.min(textBox.x, chunkBox.x)

      if (hasLeftArcs) {
        var spacing = arcHorizontalSpacing - (current.x - lastArcBorder);
        // arc too small?
        if (spacing > 0) current.x += spacing;
      }
      var rightBorderForArcs = hasRightArcs ? arcHorizontalSpacing : (hasInternalArcs ? arcSlant : 0);

      if (chunk.lineBreak ||
          current.x + boxWidth + rightBorderForArcs >= canvasWidth - 2 * margin.x) {
        row.arcs = svg.group(row.group, { 'class': 'arcs' });
        // new row
        rows.push(row);
        current.x = margin.x + (hasLeftArcs ? arcHorizontalSpacing : (hasInternalArcs ? arcSlant : 0));
        svg.remove(chunk.group);
        row = new Row();
        row.backgroundIndex = sentenceToggle;
        lastBoxChunkIndex = chunk.index - 1;
        row.index = ++rowIndex;
        svg.add(row.group, chunk.group);
        chunk.group = row.group.lastElementChild;
        $(chunk.group).children("g[class='span']").
          each(function(index, element) {
              chunk.spans[index].group = element;
          });
        $(chunk.group).find("rect[data-span-id]").
          each(function(index, element) {
              chunk.spans[index].rect = element;
          });
      }
      if (hasAnnotations) row.hasAnnotations = true;

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

      translate(chunk, foo = current.x + boxX, 0);
      chunk.textX = current.x - textBox.x + boxX;

      current.x += space + boxWidth;
    }); // chunks

    // finish the last row
    row.arcs = svg.group(row.group, { 'class': 'arcs' });
    rows.push(row);

    var arrows = {};

    var len = spanHeights.length;
    for (var i = 0; i < len; i++) {
      if (!spanHeights[i] || spanHeights[i] < arcStartHeight) spanHeights[i] = arcStartHeight;
    }

    // find out how high the arcs have to go
    $.each(data.arcs, function(arcNo, arc) {
      arc.jumpHeight = 0;
      var fromSpan = data.spans[arc.origin];
      var toSpan = data.spans[arc.target];
      if (fromSpan.lineIndex > toSpan.lineIndex) {
        var tmp = fromSpan; fromSpan = toSpan; toSpan = tmp;
      }
      var from, to;
      if (fromSpan.chunk.index == toSpan.chunk.index) {
        from = fromSpan.lineIndex;
        to = toSpan.lineIndex;
      } else {
        from = fromSpan.lineIndex + 1;
        to = toSpan.lineIndex - 1;
      }
      for (var i = from; i <= to; i++) {
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

    // draw the drag arc marker
    dragArrowId = 'annotator' + annId + '_drag_arrow';
    var arrowhead = svg.marker(defs, dragArrowId,
      5, 2.5, 5, 5, 'auto',
      {
        markerUnits: 'strokeWidth',
        'class': 'drag_fill',
      });
    svg.polyline(arrowhead, [[0, 0], [5, 2.5], [0, 5], [0.2, 2.5]]);

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

      // find the next height
      var height = 0;

      var fromIndex2, toIndex2;
      if (left.chunk.index == right.chunk.index) {
        fromIndex2 = left.lineIndex * 2;
        toIndex2 = right.lineIndex * 2;
      } else {
        fromIndex2 = left.lineIndex * 2 + 1;
        toIndex2 = right.lineIndex * 2 - 1;
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
      var ufoCatcher = originSpan.chunk.index == targetSpan.chunk.index;
      if (ufoCatcher) {
        chunkReverse =
          leftBox.x + leftBox.width / 2 < rightBox.x + rightBox.width / 2;
      }
      var ufoCatcherMod = ufoCatcher ? chunkReverse ? -0.5 : 0.5 : 1;

      for (var rowIndex = leftRow; rowIndex <= rightRow; rowIndex++) {
        var row = rows[rowIndex];
        row.hasAnnotations = true;
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
        if(((to-from)-(2*arcSlant))/7 > arc.type.length || !abbrevText) {
          // no need to (or cannot) abbreviate
          // TODO cleaner heuristic
          abbrevText = arc.type;
        }
        var text = svg.text(arcGroup, (from + to) / 2, -height, abbrevText, {
            'class': 'fill_' + arc.type,
            'data-arc-role': arc.type,
            'data-arc-origin': arc.origin,
            'data-arc-target': arc.target,
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
          path.line(from + ufoCatcherMod * arcSlant, -height).
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
          path.line(to - ufoCatcherMod * arcSlant, -height).
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
      if (!rowBox) { // older Firefox bug
        rowBox = { x: 0, y: 0, height: 0, width: 0 };
      }
      if (row.hasAnnotations) {
        rowBox.height = -rowBox.y;
        rowBox.y -= rowSpacing;
      }
      svg.rect(backgroundGroup,
        0, y + curlyY + textHeight, canvasWidth, rowBox.height + textHeight + 1, {
        'class': 'background' + row.backgroundIndex,
      });
      y += rowBox.height;
      y += textHeight;
      row.textY = y;
      translate(row, 0, y);
      y += margin.y;
    });
    y += margin.y;

    $.each(data.chunks, function(chunkNo, chunk) {
        // text positioning
        chunk.tspan.attr({
            x: chunk.textX,
            y: chunk.row.textY,
        });
        // chunk backgrounds
        if (chunk.spans.length) {
          var spansFrom, spansTo, spansType;	 
          $.each(chunk.spans, function(spanNo, span) {
            if (spansFrom == undefined || spansFrom > span.curly.from) spansFrom = span.curly.from;
            if (spansTo == undefined || spansTo < span.curly.to) spansTo = span.curly.to;
            if (span.generalType == 'trigger' || !spansType) spansType = span.type;
          });
          svg.rect(highlightGroup,
            chunk.textX + spansFrom - 1, chunk.row.textY + curlyY - 1,
            spansTo - spansFrom + 2, chunk.spans[0].curly.height + 2,
            { 'class': 'span_default span_' + spansType, opacity:0.15 });
        }
    });

    // resize the SVG
    $(svg._svg).attr('height', y).css('height', y);
    $(containerElement).attr('height', y).css('height', y);
  }

  this.getSVG = function() {
    return containerElement.html();
  };

  this.getDocumentName = function() {
    return data.document;
  };

  this.setUser = function(_user, _password) {
    user = _user;
    password = _password;
  };

  this.postChangesAndReload = function() {
    annotator.postChangesAndReloadWithCreds(user, password);
  };

  containerElement.svg({
      onLoad: this.drawInitial,
  });
};

$(function() {
  var address = window.location.href;
  var directory = window.location.hash.substr(1).split('/')[0];
  var doc;
  var lastDoc = null;
  var qmark = address.indexOf('#');
  var slashmark = address.lastIndexOf('/', qmark);
  var base = address.slice(0, slashmark + 1);
  var ajaxBase = base + 'ajax.cgi';
  var ajaxURL;
  var docListReceived = false;
  var lastHash = null;

  displayMessage = function() {
    var timer;
    var opacity;
    var message = $('#message');
    var fadeMessage = function() {
      message.css('opacity', opacity > 1 ? 1 : opacity);
      opacity -= 0.05;
      if (opacity <= 0) {
        message.css('display', 'none');
        clearInterval(timer);
        timer = 0;
      }
    };
    return function(html) {
      message.html(html).css('display', 'block');
      opacity = 2;
      if (!timer) {
        timer = setInterval(fadeMessage, 50);
      }
    };
  }();

  var getDirectory = function() {
    ajaxURL = ajaxBase + "?directory=" + directory;
    $.get(ajaxURL, function(data) {
      docListReceived = true;
      var sel = $('#document_select').html(data);
      if (doc) sel.val(doc);
      lastHash = null;
    });
  };

  $.get(ajaxBase, function(data) {
    $('#directory_select').html(data).val(directory);
    if (directory) getDirectory();
  });


  var annotator = new Annotator('#svg', function() {
    var annotator = this;

    var directoryAndDoc;
    var drawing = false;
    var saveUser;
    var savePassword;
    var updateState = function(onRenderComplete) {
      if (drawing || lastHash == window.location.hash) return;
      lastHash = window.location.hash;
      var parts = lastHash.substr(1).split('/');
      if (directory != parts[0]) {
        directory = parts[0];
        getDirectory();
        return;
      }
      var _doc = doc = parts[1];
      if (_doc == 'save' && (savePassword = parts[2]) && (savePassword = parts[3])) return;
      $('#document_select').val(_doc);

      $('#document_name').text(directoryAndDoc);
      if (!_doc || !ajaxURL) return;
      $.get(ajaxURL + "&document=" + _doc, function(jsonData) {
          if (!jsonData) {
            console.error("No JSON data");
            return;
          }
          drawing = true;
          var error = false;
          jsonData.document = _doc;
          try {
            annotator.renderData(jsonData);
          } catch (x) {
            if (x == "BadDocumentError") error = true;
            else throw(x);
          }
          drawing = false;
          if ($.isFunction(onRenderComplete)) {
            onRenderComplete.call(annotator, error);
          }
      });
    };

    var renderDocument = function(_doc, onRenderComplete) {
      doc = _doc;
      directoryAndDoc = directory + (doc ? '/' + doc : '');
      window.location.hash = '#' + directoryAndDoc;
      updateState(onRenderComplete);
    };

    annotator.postChangesAndReloadWithCreds = function(user, pass) {
      var _doc = doc;
      $.extend(annotator.ajaxOptions, {
        directory: directory,
        document: _doc,
        user: user,
        pass: pass,
      });
      $.ajax({
        type: 'POST',
        url: ajaxBase,
        data: annotator.ajaxOptions,
        error: function(req, textStatus, errorThrown) {
          console.error(textStatus, errorThrown);
        },
        success: function(response) {
          lastHash = null; // force reload
          renderDocument(_doc);
          console.log("Ajax response: ", response); // DEBUG
        }
      });
      annotator.ajaxOptions = null;
    };

    var renderSelected = function(evt, onRenderComplete) {
      doc = $('#document_select').val();
      renderDocument(doc, onRenderComplete);
      return false;
    };

    var renderToDiskAndSelectNext = function() {
      if (!savePassword) return;

      renderSelected(null, function(error) {
        var svgMarkup = annotator.getSVG();
        var doc = annotator.getDocumentName();

        var nextFunction = function(data) {
          var select = $('#document_select')[0];
          select.selectedIndex = select.selectedIndex + 1;
          if (select.selectedIndex != -1) {
            setTimeout(renderToDiskAndSelectNext, 0);
          } else {
            alert('done');
            savePassword = undefined;
          }
        };

        if (error) {
          nextFunction.call();
        } else {
          $.ajax({
            type: 'POST',
            url: ajaxBase,
            data: {
              directory: directory,
              document: doc,
              user: saveUser,
              pass: savePassword,
              svg: svgMarkup,
            },
            error: function(req, textStatus, errorThrown) {
              console.error(doc, textStatus, errorThrown);
              if (savePassword) {
                savePassword = undefined;
                alert('Error occured.\nSVG dump aborted.');
              }
            },
            success: nextFunction,
          });
        }
      });
    };
    
    var renderAllToDisk = function() {
      if (docListReceived) {
        $('#document_select')[0].selectedIndex = 1;
        annotator.forceWidth = 960; // for display in 1024-width browsers
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
    $('#directory_select').
        change(function(evt) {
          document.location.hash = $(evt.target).val();
        });

    var spanFormSubmit = function(evt) {
      spanForm.css('display', 'none');
      var type = $('#span_form input:radio:checked').val();
      if (!type) type = $('#span_free_text').val();
      if (type) { // (if not cancelled)
        annotator.ajaxOptions.type = type;
        annotator.postChangesAndReload();
      }
      return false;
    };
    var spanForm = $('#span_form').
      submit(spanFormSubmit).
      bind('reset', function(evt) {
        spanForm.css('display', 'none');
      });
    spanForm.find('input:radio').not('#span_free_entry').click(spanFormSubmit);
    $('#del_span_button').click(annotator.deleteSpan);

    var arcSubmit = function(type) {
      annotator.ajaxOptions.type = type;
      annotator.postChangesAndReload();
    }
    var arcFormSubmit = function(evt) {
      arcForm.css('display', 'none');
      var type = $('#arc_form input:radio:checked').val();
      if (!type) type = $('#arc_free_text').val();
      if (type) { // (if not cancelled)
        arcSubmit(type);
      }
      return false;
    };
    var arcForm = $('#arc_form').
      submit(arcFormSubmit).
      bind('reset', function(evt) {
        arcForm.css('display', 'none');
      });
    annotator.fillArcTypesAndDisplayForm = function(originType, targetType, arcType) {
      $.get(ajaxBase, {
        action: 'arctypes',
        origin: originType,
        target: targetType,
      }, function(jsonData) {
        var markup = [];
	if (jsonData.message) {
	  displayMessage(jsonData.message);
	  //console.log(jsonData.message);
	}
	if(jsonData.types && jsonData.types.length != 0) {
	  $.each(jsonData.types, function(fieldsetNo, fieldset) {
	    markup.push('<fieldset>');
	    markup.push('<legend>' + fieldset[0] + '</legend>');
	    $.each(fieldset[1], function(roleNo, role) {
	      markup.push('<input name="arc_type" id="arc_' + role + '" type="radio" value="' + role + '"/>');
	      markup.push('<label for="arc_' + role + '">' + role + '</label> ');
	    });
	    markup.push('</fieldset>');
	  });
	  markup = markup.join('');
	  $('#arc_roles').html(markup);
	  var el = $('#arc_' + arcType);
	  if (el.length) {
	    el[0].checked = true;
	  } else {
	    $('#arc_free_text').val(arcType);
	    $('#arc_free_entry')[0].checked = true;
	  }
	  arcForm.find('#arc_roles input:radio').click(arcFormSubmit);
	  $('#arc_form').css('display', 'block');
	}
      });
    };
    arcForm.find('input:radio').not('#arc_free_entry').click(arcFormSubmit);
    $('#del_arc_button').click(annotator.deleteArc);

    var authFormSubmit = function(evt) {
      var user = $('#auth_user').val();
      var password = $('#auth_pass').val();
      $.ajax({
        type: 'POST',
        url: ajaxBase,
        data: {
          action: 'auth',
          user: user,
          pass: password,
        },
        error: function(req, textStatus, errorThrown) {
          // TODO: check if it is the auth error
          authForm.css('display', 'block');
          $('#auth_user').select().focus();
          return false;
        },
        success: function(response) {
          console.log(response);
          annotator.setUser(user, password);
          $('#auth_button').val('Logout');
          $('#auth_user').val('');
          $('#auth_pass').val('');
        }
      });
      authForm.css('display', 'none');
      return false;
    };
    var authForm = $('#auth_form').
      submit(authFormSubmit).
      bind('reset', function(evt) {
        authForm.css('display', 'none');
      });
    $('#auth_button').click(function() {
      var auth_button = $('#auth_button');
      if (auth_button.val() == 'Login') {
        $('#auth_form').css('display', 'block');
        $('#auth_user').select().focus();
      } else {
        annotator.setUser();
        auth_button.val('Login');
      }
    });

    directoryAndDoc = directory + (doc ? '/' + doc : '');
    updateState(doc);
    if (savePassword) {
      renderAllToDisk();
    } else {
      setInterval(updateState, 200); // TODO okay?
    }
  });


  $(window).resize(function(evt) {
    renderSelected();
  });
});
