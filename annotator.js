// -*- Mode: JavaScript; tab-width: 2; indent-tabs-mode: nil; -*-
// vim:set ft=javascript ts=2 sw=2 sts=2 cindent:

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

var profileStart = new Date().getTime();
var profilestart = function(str) {
  profileStart = -new Date().getTime();
}
var profileend = function(str) {
  console.debug(new Date().getTime() + profileStart, str);
}
var profile = function(str) {
} // profile
// XXX TODO: what is this? "profilefoo" doesn't appear in other places
profilefoo = []

var displayMessages;
var displayMessage;
var hideInfo;
var infoBoxVisible = 0;
var messageOpacity = 0.9;
var infoBoxTimer;
var displayInfo = function(html, evt) {
    var infoBox = $('#infopopup');
    infoBox.html(html).css('display', 'block');
    infoBox.css({ 'opacity' : 1, 'top': evt.pageY-40-infoBox.height(), 'left':evt.pageX });
    infoBoxVisible = true;
    if (infoBoxTimer) {
	clearInterval(infoBoxTimer);
	infoBoxTimer = 0;
    }
}

var displayMessagesAndCheckForErrors = function(response) {
  if (response) {
    var no_errors = true;

    if (response.messages) {
	displayMessages(response.messages);
	$.each(response.messages, function(messageNo, message) {
	    if (message[1] == 'error') {
		no_errors = false;
	    }
	})
    } 

    // TODO: remove this once all users of the old single-message
    // protocol have been weeded out
    if (response.message) {
      displayMessage("<b>[NOTE: server received the following message directly as 'response.message'. Use display_message() instead]</b> " + response.message, false, -1);
    }
    if (response.error) {
	displayMessage("<b>[NOTE: server received the following message directly as 'response.error'. Use display_message() instead]</b> " + response.error, true, -1);
	no_errors = false;
    }

    return no_errors;
  }
  return false;
}

// SVG Annotation tool
var Annotator = function(containerElement, onStart) {
  // settings
  var margin = { x: 2, y: 1 };
  // fine tuning specifically for box text margins
  var boxTextMargin = { x: 0, y: 0 };
  var space = 4;
  var boxSpacing = 1;
  var curlyHeight = 4;
  var arcSpacing = 9; //10;
  var arcSlant = 15; //10;
  var arcStartHeight = 19; //23; //25;
  var arcHorizontalSpacing = 25;
  var rowSpacing = -5;          // for some funny reason approx. -10 gives "tight" packing.
  var dashArray = '3,3';
  var sentNumMargin = 20;
  var smoothArcCurves = true;   // whether to use curves (vs lines) in arcs
  var smoothArcSteepness = 0.5; // steepness of smooth curves (control point)
  var reverseArcControlx = 5;   // control point distance for "UFO catchers"
  var shadowSize = 5;
  var shadowStroke = 5;
  var editedSpanSize = 7;
  var editedArcSize = 3;
  var editedStroke = 7;

  var undefined; // prevents evil "undefined = 17" attacks

  this.spanAbbreviations = {};
  this.arcAbbreviations = {};

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
  var highlightSpans;
  var arcDragOrigin;
  var arcDragArc;
  var arcDragOriginBox;
  var arcDragOriginGroup;
  var dragArrowId;
  var highlightGroup;
  var curlyY;
  this.keymap = {};
  var editedSent;
  this.selectedRange = null;

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
      var mods = [];
      if (span.Negation) mods.push("Negated");
      if (span.Speculation) mods.push("Speculated");
      if (mods.length) mods = '<div>' + mods.join(', ') + '</div>';
      var info = '<div><span class="info_id">' + id + '</span>' + ' ' + '<span class="info_type">' + span.type + '</span>' + mods + '</div>';
      info += '<div>"'+data.text.substring(span.from, span.to)+'"</div>';

      var idtype;
      if (span.info) {
        info += span.info.text;
        idtype = 'info_' + span.info.type;
      }
      $('#infopopup')[0].className = idtype;
      displayInfo(info, evt);
      highlight = svg.rect(highlightGroup,
        span.chunk.textX + span.curly.from - 1, span.chunk.row.textY + curlyY - 1,
        span.curly.to + 2 - span.curly.from, span.curly.height + 2,
        { 'class': 'span_default span_' + span.type });
      if (arcDragOrigin) {
        target.parent().addClass('highlight');
      } else {
        highlightArcs = $(svgElement).
            find('g[data-from="' + id + '"], g[data-to="' + id + '"]').
            addClass('highlight');
        var spans = {};
        spans[id] = true;
        var spanIds = [];
        $.each(span.incoming, function(arcNo, arc) {
            spans[arc.origin] = true;
        });
        $.each(span.outgoing, function(arcNo, arc) {
            spans[arc.target] = true;
        });
        $.each(spans, function(spanId, dummy) {
            spanIds.push('rect[data-span-id="' + spanId + '"]');
        });
        highlightSpans = $(svgElement).
            find(spanIds.join(', ')).
            parent().
            addClass('highlight');
      }
      forceRedraw();
    } else if (!arcDragOrigin && (id = target.attr('data-arc-role'))) {
      var originSpanId = target.attr('data-arc-origin');
      var targetSpanId = target.attr('data-arc-target');
      // TODO: remove special-case processing, introduce way to differentiate
      // symmetric relations in general
      var info;
      if (target.attr('data-arc-role') == "Equiv") {
	  // symmetric
	  info = '<div class="info_arc">' + originSpanId + ' ' + target.attr('data-arc-role') + ' ' + targetSpanId +'</div>'
      } else {
	  // directed
	  info = '<div class="info_arc">' + originSpanId + ' &#8594; ' + target.attr('data-arc-role') + ':' + targetSpanId +'</div>'
      }
      $('#infopopup')[0].className = "";
      displayInfo(info, evt);
      highlightArcs = $(svgElement).
          find('g[data-from="' + originSpanId + '"][data-to="' + targetSpanId + '"]').
          addClass('highlight');
      highlightSpans = $(svgElement).
          find('rect[data-span-id="' + originSpanId + '"], rect[data-span-id="' + targetSpanId + '"]').
          parent().
          addClass('highlight');
    } else if (id = target.attr('data-sent')) {
      var info = data.sentInfo[id];
      if (info) {
        displayInfo(info.text, evt);
      }
    }
  };

  var mouseOut = function(evt) {
      if (infoBoxVisible) {
	  hideInfo();
      }
    var target = $(evt.target);
    if (arcDragOrigin && arcDragOrigin != target.attr('data-span-id')) {
      target.parent().removeClass('highlight');
    }
    if (highlight) {
      svg.remove(highlight);
      highlight = undefined;
    }
    if (highlightSpans) {
      highlightArcs.removeClass('highlight');
      highlightSpans.removeClass('highlight');
      highlightSpans = undefined;
    }
    forceRedraw();
  };

  this.deleteSpan = function(evt) {
    var confirmMode = $('#confirm_mode')[0].checked;
    if (confirmMode && !confirm("Are you sure you want to delete this annotation?")) {
      return;
    }
    $('#span_form').css('display', 'none');
    annotator.keymap = {};
    annotator.ajaxOptions.action = 'unspan';
    annotator.postChangesAndReload();
  };

  this.deleteArc = function(evt) {
    var confirmMode = $('#confirm_mode')[0].checked;
    if (confirmMode && !confirm("Are you sure you want to delete this annotation?")) {
      return;
    }
    var eventDataId = $(evt.target).attr('data-arc-ed');
    $('#arc_form').css('display', 'none');
    annotator.keymap = {};
    annotator.ajaxOptions.action = 'unarc';
    annotator.postChangesAndReload();
  };

  var dblClick = function(evt) {
    if (!annotator.user) return;
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
        type: type,
        old: type,
      };
      var eventDescId = target.attr('data-arc-ed');
      if (eventDescId) {
        var eventDesc = data.eventDescs[eventDescId];
        annotator.ajaxOptions['left'] = eventDesc.leftSpans.join(',');
        annotator.ajaxOptions['right'] = eventDesc.rightSpans.join(',');
      }
      $('#arc_origin').text(originSpan.type+' ("'+data.text.substring(originSpan.from, originSpan.to)+'")');
      $('#arc_target').text(targetSpan.type+' ("'+data.text.substring(targetSpan.from, targetSpan.to)+'")');
      var arcId = originSpanId + '--' + type + '--' + targetSpanId;
      annotator.fillArcTypesAndDisplayForm(evt, originSpan.type, targetSpan.type, type, arcId);
      
    // if not, then do we edit a span?
    } else if (id = target.attr('data-span-id')) {
      window.getSelection().removeAllRanges();
      var span = data.spans[id];
      annotator.ajaxOptions = {
        action: 'span',
        from: span.from,
        to: span.to,
        id: id,
      };
      var spanText = data.text.substring(span.from, span.to);
      annotator.fillSpanTypesAndDisplayForm(evt, spanText, span);
    }
  };

  var mouseDown = function(evt) {
    if (!annotator.user || arcDragOrigin) return;
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
    if (!annotator.user) return;
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
        annotator.fillArcTypesAndDisplayForm(evt, originSpan.type, targetSpan.type);
      }
      svg.remove(arcDragArc);
      arcDragOrigin = undefined;
    } else if (!evt.ctrlKey) {
      // if not, then is it span selection? (ctrl key cancels)
      var sel = window.getSelection();
      if (sel.rangeCount) {
        annotator.selectedRange = sel.getRangeAt(0);
      }
      var chunkIndexFrom = sel.anchorNode && $(sel.anchorNode.parentNode).attr('data-chunk-id');
      var chunkIndexTo = sel.focusNode && $(sel.focusNode.parentNode).attr('data-chunk-id');
      if (chunkIndexFrom != undefined && chunkIndexTo != undefined) {
        var chunkFrom = data.chunks[chunkIndexFrom];
        var chunkTo = data.chunks[chunkIndexTo];
        var selectedFrom = chunkFrom.from + sel.anchorOffset;
        var selectedTo = chunkTo.from + sel.focusOffset;
        sel.removeAllRanges();

        // trim
        while (selectedFrom < selectedTo && " \n\t".indexOf(data.text.substr(selectedFrom, 1)) != -1) selectedFrom++;
        while (selectedFrom < selectedTo && " \n\t".indexOf(data.text.substr(selectedTo - 1, 1)) != -1) selectedTo--;

        if (selectedFrom == selectedTo) return; // simple click (zero-width span)
        if (selectedFrom > selectedTo) {
          var tmp = selectedFrom; selectedFrom = selectedTo; selectedTo = tmp;
        }
        annotator.ajaxOptions = {
          action: 'span',
          from: selectedFrom,
          to: selectedTo,
        };
        var spanText = data.text.substring(selectedFrom, selectedTo);
        if (spanText.indexOf("\n") != -1) {
          displayMessage("Error: cannot annotate across a sentence break", true);
        } else {
	        annotator.fillSpanTypesAndDisplayForm(evt, spanText);
        }
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
      span.incoming = []; // protect from shallow copy
      span.outgoing = [];
      span.id = eventDesc.id;
      data.spans[eventDesc.id] = span;
    });
    $.each(data.modifications, function(modNo, mod) {
      if (!data.spans[mod[2]]) {
        displayMessage('<strong>ERROR</strong><br/>Event ' + mod[2] + ' (referenced from modification ' + mod[0] + ') does not occur in document ' + data.document + '<br/>(please correct the source data)', true, 5);
        throw "BadDocumentError";
      }
      data.spans[mod[2]][mod[1]] = true;
    });
    $.each(data.equivs, function(equivNo, equiv) {
      equiv[0] = "*" + equivNo;
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
        eventDesc.leftSpans = equivSpans.slice(0, i);
        eventDesc.rightSpans = equivSpans.slice(i);
      }
    });
    data.sentInfo = {};
    $.each(data.infos, function(infoNo, info) {
      // TODO error handling
      if (info[0] instanceof Array && info[0][0] == 'sent') { // [['sent', 7], 'Type', 'Text']
        var sent = info[0][1];
        var text = info[2];
        if (data.sentInfo[sent]) {
          text = data.sentInfo[sent].text + '<br/>' + text;
        }
        data.sentInfo[sent] = { type: info[1], text: text };
      } else if (info[0] in data.spans) {
        var span = data.spans[info[0]];
        if (!span.info) {
          span.info = { type: info[1], text: info[2] };
        } else {
          span.info.type = info[1];
          span.info.text += "<br/>" + info[2];
        }
	// prioritize type setting when multiple infos are present: Error > Warning > Incomplete
        if ((info[1].indexOf('Error') != -1) ||
	    (info[1].indexOf('Warning') != -1 && (!span.shadowClass || span.shadowClass.indexOf("Error") == -1)) ||
            (info[1].indexOf('Incomplete') != -1 && (!span.shadowClass || (span.shadowClass.indexOf("Error") == -1 && span.shadowClass.indexOf("Warning") == -1)))) {
	    span.shadowClass = info[1]
        }
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
    // and copy spans to sortedSpans array
    var sortedSpans = [];
    var numChunks = data.chunks.length;
    for (spanId in data.spans) {
      var span = data.spans[spanId];
      sortedSpans.push(span);
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
      if (!origin.chunk) {
	// TODO: include missing trigger ID in error message
        displayMessage('<strong>ERROR</strong><br/>Trigger for event "' + eventDesc.id + '" not found in ' + data.document + '<br/>(please correct the source data)', true, 5);
        throw "BadDocumentError";
      }
      var here = origin.chunk.index;
      $.each(eventDesc.roles, function(roleNo, role) {
        var target = data.spans[role.targetId];
        if (!target) {
          displayMessage('<strong>ERROR</strong><br/>"' + role.targetId + '" (referenced from "' + eventDesc.id + '") not found in ' + data.document + '<br/>(please correct the source data)', true, 5);
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
        if (eventDesc.equiv) {
          arc.equiv = true;
          eventDesc.equivArc = arc;
          arc.eventDescId = eventNo;
        }
        origin.totalDist += dist;
        origin.numArcs++;
        target.totalDist += dist;
        target.numArcs++;
        data.arcs.push(arc);
        target.incoming.push(arc);
        origin.outgoing.push(arc);
      }); // roles
    }); // eventDescs

    // last edited highlighting
    if (annotator.edited) {
      $.each(annotator.edited, function(editedNo, edited) {
        if (edited[0] == 'sent') {
          editedSent = edited[1];
        } else if (edited[0] == 'equiv') { // [equiv, Equiv, T1]
          $.each(data.equivs, function(equivNo, equiv) {
            if (equiv[1] == edited[1]) {
              var len = equiv.length;
              for (var i = 2; i < len; i++) {
                if (equiv[i] == edited[2]) {
                  // found it
                  len -= 3;
                  for (var i = 1; i <= len; i++) {
                    var arc = data.eventDescs[equiv[0] + "*" + i].equivArc;
                    arc.edited = true;
                  }
                  return; // next equiv
                }
              }
            }
          });
        } else {
          editedSent = null;
          var span = data.spans[edited[0]];
          if (span) {
            if (edited.length == 3) { // arc
              $.each(span.outgoing, function(arcNo, arc) {
                if (arc.target == edited[2] && arc.type == edited[1]) {
                  arc.edited = true;
                }
              });
            } else { // span
              span.edited = true;
            }
          }
        }
      });
    }
    annotator.edited = null;

    // sort the spans for linear order
    sortedSpans.sort(function(a, b) {
      var tmp = a.from + a.to - b.from - b.to;
      if (tmp) {
        return tmp < 0 ? -1 : 1;
      }
      return 0;
    });

    // mark curlies where needed
    var lastSpan = null;
    var towerId = 0;
    $.each(sortedSpans, function(i, span) {
      if (!lastSpan || (lastSpan.from != span.from || lastSpan.to != span.to)) {
        towerId++;
      }
      span.towerId = towerId;
      span.avgDist = span.totalDist / span.numArcs;
      lastSpan = span;
    }); // sortedSpans

    var spanAnnTexts = {};
    data.spanAnnTexts = [];
    data.towers = {};

    var sortComparator = function(a, b) {
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
      tmp = a.refedIndexSum - b.refedIndexSum;
      if (tmp) {
        return tmp < 0 ? -1 : 1;
      }
      // if no other criterion is found, sort by type to maintain
      // consistency
      // TODO: isn't there a cmp() in JS?
      if (a.type < b.type) {
        return -1;
      } else if (a.type > b.type) {
        return 1;
      }
      
      return 0;
    };

    for (var i = 0; i < 2; i++) {
      // preliminary sort to assign heights for basic cases
      // (first round) and cases resolved in the previous
      // round(s).
      $.each(data.chunks, function(chunkNo, chunk) {
        chunk.spans.sort(sortComparator); // sort
        $.each(chunk.spans, function(spanNo, span) {
          span.indexNumber = spanNo;
          span.refedIndexSum = 0;
        });
      });
      // resolved cases will now have indexNumber set
      // to indicate their relative order. Sum those for referencing cases
      $.each(data.arcs, function(arcNo, arc) {
        data.spans[arc.origin].refedIndexSum += data.spans[arc.target].indexNumber;
      });
    }

    // Sort spans in chunks for drawing purposes
    $.each(data.chunks, function(chunkNo, chunk) {
      // and make the next sort take this into account. Note that this will
      // now resolve first-order dependencies between sort orders but not
      // second-order or higher.
      chunk.spans.sort(sortComparator); // sort
      $.each(chunk.spans, function(spanNo, span) {
        span.chunk = chunk;
        span.text = chunk.text.substring(span.from, span.to);
        if (!data.towers[span.towerId]) {
          data.towers[span.towerId] = [];
          span.drawCurly = true;
        }
        data.towers[span.towerId].push(span);

	// Find the most appropriate abbreviation according to text
        // width
	span.abbrevText = span.type;
	var abbrevIdx = 0;
	var maxLength = (span.to - span.from) / 0.8;
	while (span.abbrevText.length > maxLength &&
            annotator.spanAbbreviations[span.type] &&
            annotator.spanAbbreviations[span.type][abbrevIdx]) {
          span.abbrevText = annotator.spanAbbreviations[span.type][abbrevIdx];
          abbrevIdx++;
	}

        if (!spanAnnTexts[span.abbrevText]) {
          spanAnnTexts[span.abbrevText] = true;
          data.spanAnnTexts.push(span.abbrevText);
        }
      }); // chunk.spans
    }); // chunks

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

  // TODO do the towerId and lineIndex overlap?

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

  this.drawing = false;
  this.redraw = false;

  var renderDataReal = function(_data) {
    $(containerElement).css('display', 'block');
    if (this.drawing) {
      Annotator.actionsAllowed(true);
      return;
    }
    this.redraw = false;
    this.drawing = true;

    try {
      if (_data) setData(_data);

      if (data.mtime) {
	  // we're getting seconds and need milliseconds
	  //$('#document_ctime').text("Created: " + Annotator.formatTime(1000 * data.ctime)).css("display", "inline");
	  $('#document_mtime').text("Last modified: " + Annotator.formatTime(1000 * data.mtime)).css("display", "inline");
      } else {
	  //$('#document_ctime').css("display", "none");
	  $('#document_mtime').css("display", "none");
      }


      svg.clear(true);
      var defs = svg.defs();
      var filter = $('<filter id="Gaussian_Blur"><feGaussianBlur in="SourceGraphic" stdDeviation="2" /></filter>');
      svg.add(defs, filter);
      if (!data || data.length == 0) return;
      canvasWidth = this.forceWidth || $(containerElement).width();
      $(svgElement).width(canvasWidth);
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
        chunk.row = undefined; // reset
        textSpans.span(chunk.text + ' ', {
            id: makeId('chunk' + chunk.index),
            'data-chunk-id': chunk.index,
        });
      });
      var text = svg.text(textGroup, 0, 0, textSpans, {'class': 'text'});
      var textHeight = text.getBBox().height;

      // measure annotations
      var dummySpan = svg.group({ 'class': 'span' });
      var spanAnnBoxes = {};
      $.each(data.spanAnnTexts, function(textNo, text) {
        var spanText = svg.text(dummySpan, 0, 0, text);
        spanAnnBoxes[text] = spanText.getBBox();
      }); // data.spanAnnTexts
      svg.remove(dummySpan);

      // find biggest annotation in each tower
      $.each(data.towers, function(towerNo, tower) {
        var biggestBox = { width: 0 };
        $.each(tower, function(spanNo, span) {
          var annBox = spanAnnBoxes[span.abbrevText];
          if (annBox.width > biggestBox.width) biggestBox = annBox;
        }); // tower
        $.each(tower, function(spanNo, span) {
          span.annBox = biggestBox;
        }); // tower
      }); // data.towers

      var current = { x: margin.x + sentNumMargin, y: margin.y }; // TODO: we don't need some of this?
      var rows = [];
      var spanHeights = [];
      var sentenceToggle = 0;
      var sentenceNumber = 0;
      var row = new Row();
      row.sentence = ++sentenceNumber;
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
          span.group = svg.group(chunk.group, {
            'class': 'span',
            id: makeId('span_' + span.id),
          });

          // measure the text span
          var xFrom = 0;
          if (span.from != chunk.from) {
            var measureText = svg.text(textGroup, 0, 0,
              chunk.text.substr(0, span.from - chunk.from));
            xFrom = measureText.getBBox().width;
            svg.remove(measureText);
          }
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

          var spanBox = span.annBox;
          var xx = spanBox.x + x;
          var yy = spanBox.y + y;
          var hh = spanBox.height;

          // text margin fine-tuning
          yy += boxTextMargin.y;
          hh -= 2*boxTextMargin.y;
          
          var rectClass = 'span_' + span.type + ' span_default';

         // attach e.g. "False_positive" into the type
         if (span.info && span.info.type) { rectClass += ' '+span.info.type; }
         var bx = xx - margin.x - boxTextMargin.x;
         var by = yy - margin.y;
         var bw = spanBox.width + 2 * margin.x + 2 * boxTextMargin.x;
         var bh = hh + 2 * margin.y;
         var shadowRect;
         var editedRect;
         if (span.edited) {
             editedRect = svg.rect(span.group,
                 bx - editedSpanSize, by - editedSpanSize,
                 bw + 2 * editedSpanSize, bh + 2 * editedSpanSize, {

                 // filter: 'url(#Gaussian_Blur)',
                 'class': "shadow_EditHighlight",
                 rx: editedSpanSize,
                 ry: editedSpanSize,
             });
         }
         if (span.shadowClass) {
             shadowRect = svg.rect(span.group,
                 bx - shadowSize, by - shadowSize,
                 bw + 2 * shadowSize, bh + 2 * shadowSize, {

                 filter: 'url(#Gaussian_Blur)',
                 'class': "shadow_" + span.shadowClass,
                 rx: shadowSize,
                 ry: shadowSize,
             });
         }
         span.rect = svg.rect(span.group,
             bx, by, bw, bh, {
             'class': rectClass,
             rx: margin.x,
             ry: margin.y,
             'data-span-id': span.id,
             'strokeDashArray': span.Speculation ? dashArray : undefined,
           });
          var rectBox = span.rect.getBBox();

          var yAdjust = placeReservation(span, rectBox, reservations);
          // this is monotonous due to sort:
          span.height = yAdjust + hh + 3 * margin.y + curlyHeight + arcSpacing;
          spanHeights[span.lineIndex * 2] = span.height;
          $(span.rect).attr('y', yy - margin.y - yAdjust);
          if (shadowRect) {
              $(shadowRect).attr('y', yy - shadowSize - margin.y - yAdjust);
          }
          if (editedRect) {
              $(editedRect).attr('y', yy - editedSpanSize - margin.y - yAdjust);
          }
          if (span.Negation) {
            svg.path(span.group, svg.createPath().
                move(xx, yy - margin.y - yAdjust).
                line(xx + spanBox.width,
                  yy + hh + margin.y - yAdjust),
                { 'class': 'negation' });
            svg.path(span.group, svg.createPath().
                move(xx + spanBox.width, yy - margin.y - yAdjust).
                line(xx, yy + hh + margin.y - yAdjust),
                { 'class': 'negation' });
          }
          var spanText = svg.text(span.group, x, y - yAdjust, span.abbrevText);

          // Make curlies to show the span
          if (span.drawCurly) {
            var bottom = yy + hh + margin.y - yAdjust;
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
          current.x = margin.x + sentNumMargin +
              (hasLeftArcs ? arcHorizontalSpacing : (hasInternalArcs ? arcSlant : 0));
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
        if (chunk.newSentence) row.sentence = ++sentenceNumber;

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

        translate(chunk, current.x + boxX, 0);
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
            from = sentNumMargin;
          }

          if (rowIndex == rightRow) {
            to = rightBox.x + (chunkReverse ? rightBox.width : 0);
          } else {
            to = canvasWidth - 2 * margin.y;
          }

	  var abbrevText = arc.type;
	  var abbrevIdx = 0;
	  var maxLength = ((to-from)-(2*arcSlant))/7;
	  while (abbrevText.length > maxLength &&
		 annotator.arcAbbreviations[arc.type] &&
		 annotator.arcAbbreviations[arc.type][abbrevIdx]) {
	      abbrevText = annotator.arcAbbreviations[arc.type][abbrevIdx];
	      abbrevIdx++;
	  }

          var shadowGroup;
          if (arc.shadowClass || arc.edited) shadowGroup = svg.group(arcGroup);
          var options = {
            'class': 'fill_' + arc.type,
            'data-arc-role': arc.type,
            'data-arc-origin': arc.origin,
            'data-arc-target': arc.target,
          };
          if (arc.equiv) {
            options['data-arc-ed'] = arc.eventDescId;
          }
          var text = svg.text(arcGroup, (from + to) / 2, -height, abbrevText, options);
          var textBox = text.getBBox();
          if (arc.edited) {
            svg.rect(shadowGroup,
                textBox.x - editedArcSize, textBox.y - editedArcSize,
                textBox.width + 2 * editedArcSize, textBox.height + 2 * editedArcSize, {
                  // filter: 'url(#Gaussian_Blur)',
                  'class': "shadow_EditHighlight",
                  rx: editedArcSize,
                  ry: editedArcSize,
            });
          }
          if (arc.shadowClass) {
            svg.rect(shadowGroup,
                textBox.x - shadowSize, textBox.y - shadowSize,
                textBox.width + 2 * shadowSize, textBox.height + 2 * shadowSize, {
                  filter: 'url(#Gaussian_Blur)',
                  'class': "shadow_" + arc.shadowClass,
                  rx: shadowSize,
                  ry: shadowSize,
            });
          }
          var textStart = textBox.x - margin.x;
          var textEnd = textStart + textBox.width + 2 * margin.x;
          if (from > to) {
            var tmp = textStart; textStart = textEnd; textEnd = tmp;
          }

          var path;
          path = svg.createPath().move(textStart, -height);
          if (rowIndex == leftRow) {
              var cornerx = from + ufoCatcherMod * arcSlant;
              // for normal cases, should not be past textStart even if narrow
              if (!ufoCatcher && cornerx > textStart) { cornerx = textStart; }
              if (smoothArcCurves) {
                  var controlx = ufoCatcher ? cornerx + 2*ufoCatcherMod*reverseArcControlx : smoothArcSteepness*from+(1-smoothArcSteepness)*cornerx;
                  line = path.line(cornerx, -height).
                      curveQ(controlx, -height, from, leftBox.y + (leftToRight || arc.equiv ? leftBox.height / 2 : margin.y));
              } else {
                  path.line(cornerx, -height).
                      line(from, leftBox.y + (leftToRight || arc.equiv ? leftBox.height / 2 : margin.y));
              }
          } else {
              path.line(from, -height);
          }
          svg.path(arcGroup, path, {
              markerEnd: leftToRight || arc.equiv ? undefined : ('url(#' + arrows[arc.type] + ')'),
              'class': 'stroke_' + arc.type,
              'strokeDashArray': arc.equiv ? dashArray : undefined,
          });
          if (arc.edited) {
            svg.path(shadowGroup, path, {
                'class': 'shadow_EditHighlight_arc',
                strokeWidth: editedStroke,
            });
          }
          if (arc.shadowClass) {
            svg.path(shadowGroup, path, {
                'class': 'shadow_' + arc.shadowClass,
                strokeWidth: shadowStroke,
            });
          }
          path = svg.createPath().move(textEnd, -height);
          if (rowIndex == rightRow) {
              // TODO: duplicates above in part, make funcs
              var cornerx  = to - ufoCatcherMod * arcSlant;
              // for normal cases, should not be past textEnd even if narrow
              if (!ufoCatcher && cornerx < textEnd) { cornerx = textEnd; }
              if (smoothArcCurves) {
                  var controlx = ufoCatcher ? cornerx - 2*ufoCatcherMod*reverseArcControlx : smoothArcSteepness*to+(1-smoothArcSteepness)*cornerx;
                  path.line(cornerx, -height).
                      curveQ(controlx, -height, to, rightBox.y + (leftToRight && !arc.equiv ? margin.y : rightBox.height / 2));
              } else {
                  path.line(cornerx, -height).
                      line(to, rightBox.y + (leftToRight && !arc.equiv ? margin.y : rightBox.height / 2));
              }
          } else {
            path.line(to, -height);
          }
          svg.path(arcGroup, path, {
              markerEnd: leftToRight && !arc.equiv ? 'url(#' + arrows[arc.type] + ')' : undefined,
              'class': 'stroke_' + arc.type,
              'strokeDashArray': arc.equiv ? dashArray : undefined,
          });
          if (arc.edited) {
            svg.path(shadowGroup, path, {
                'class': 'shadow_EditHighlight_arc',
                strokeWidth: editedStroke,
            });
          }
          if (shadowGroup) {
            svg.path(shadowGroup, path, {
                'class': 'shadow_' + arc.shadowClass,
                strokeWidth: shadowStroke,
            });
          }
        } // arc rows
      }); // arcs

      var y = margin.y;
      var sentNumGroup = svg.group({'class': 'sentnum'});
      var currentSent;
      $.each(rows, function(rowId, row) {
        if (row.sentence) {
          currentSent = row.sentence;
        }
        var rowBox = row.group.getBBox();
        if (!rowBox) { // older Firefox bug
          rowBox = { x: 0, y: 0, height: 0, width: 0 };
        }
        if (row.hasAnnotations) {
          rowBox.height = -rowBox.y+rowSpacing;
        }
        svg.rect(backgroundGroup,
          0, y + curlyY + textHeight, canvasWidth, rowBox.height + textHeight + 1, {
          'class': 'background' +
              (editedSent && editedSent == currentSent ?
               'Highlight' : row.backgroundIndex),
        });
        y += rowBox.height;
        y += textHeight;
        row.textY = y;
        if (row.sentence) {
          var text = svg.text(sentNumGroup, sentNumMargin - margin.x, y, '' + row.sentence, {
              'data-sent': row.sentence,
            });
          var sentInfo = data.sentInfo[row.sentence];
          if (sentInfo) {
            var box = text.getBBox();
            svg.remove(text);
            shadowRect = svg.rect(sentNumGroup,
                box.x - shadowSize, box.y - shadowSize,
                box.width + 2 * shadowSize, box.height + 2 * shadowSize, {

                filter: 'url(#Gaussian_Blur)',
                'class': "shadow_" + sentInfo.type,
                rx: shadowSize,
                ry: shadowSize,
                'data-sent': row.sentence,
            });
            var text = svg.text(sentNumGroup, sentNumMargin - margin.x, y, '' + row.sentence, {
              'data-sent': row.sentence,
            });
          }
        }
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

      svg.path(sentNumGroup, svg.createPath().
        move(sentNumMargin, 0).
        line(sentNumMargin, y));
      // resize the SVG
      $(svg._svg).attr('height', y).css('height', y);
      $(containerElement).attr('height', y).css('height', y);

      this.drawing = false;
      if (this.redraw) {
        this.redraw = false;
        renderDataReal();
      }
    } catch(x) {
      annotator.clearSVG();
      this.drawing = false;
    }
    Annotator.actionsAllowed(true);
  };

  this.renderData = function(_data) {
    Annotator.actionsAllowed(false);
    setTimeout(function() { renderDataReal(_data); }, 0);
  };

  this.getSVG = function() {
    return containerElement.html();
  };

  this.getDocumentName = function() {
    return data.document;
  };

  containerElement.svg({
      onLoad: this.drawInitial,
  });

  this.clearSVG = function() {
    svg.clear();
    $(containerElement).css('display', 'none');
  }
};

(function() {
  var monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

  var unitAgo = function(n, unit) {
    if (n == 1) return "" + n + " " + unit + " ago";
    return "" + n + " " + unit + "s ago";
  }

  Annotator.formatTime = function(time) {
    if (time == -1000) {
	return "never";
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
})();


$(function() {
  var undefined; // prevents evil "undefined = 17" attacks

  var address = window.location.href;
  var directory = window.location.hash.substr(1).split('/')[0];
  var doc;
  var directories;
  var lastDoc = null;
  var qmark = address.indexOf('#');
  var slashmark = address.lastIndexOf('/', qmark);
  var base = address.slice(0, slashmark + 1);
  var ajaxBase = base + 'ajax.cgi';
  var docListReceived = false;
  var lastHash = null;
  var formDisplayed = false;
  var formMargin = 50;
  var minFormElementHeight = 50;

  var messages = [];
  var messageRefresh = 100; // milliseconds
  var messageOpacityDecrease = messageRefresh / 1000;
  var messageContainer = $('#messages');

  var spanFormHTML;

  setInterval(function() {
    var opacity;
    var removed = [];
    $.each(messages, function(messageNo, message) {
      if (message.opacity == -1) {
        opacity = messageOpacity;
      } else {
        opacity = message.opacity -= messageOpacityDecrease;
      }
      if (opacity <= 0) {
        message.element.remove();
        removed.push(messageNo);
        return;
      } else if (opacity > messageOpacity) {
        opacity = messageOpacity;
      }
      message.element.css('opacity', opacity);
    });
    removed = removed.sort().reverse();
    $.each(removed, function(removedNo, messageNo) {
      messages.splice(messageNo, 1);
    });
  }, messageRefresh);
  displayMessages = function(msgs) {
    if (msgs === false) {
      $.each(messages, function(messageNo, message) {
        message.opacity = -0.5; // (less than zero, and not -1, so it will trigger deletion)
      });
    } else {
      $.each(msgs, function(msgNo, msg) {
        var message = {};
	try {
	    message.element = $('<div class="' + msg[1] + '">' + msg[0] + '</div>');
	}
	catch(x) {
	    escaped = msg[0].replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
	    message.element = $('<div class="error"><b>[ERROR: could not display the following message normally due to malformed XML:]</b><br/>' + escaped + '</div>');
	}
        messageContainer.append(message.element);
	if (msg[2] === undefined) {
	    msg[2] = 3;
	}
        message.opacity = msg[2] != -1 ? msg[2] : -1;
        if (msg[2] == -1) {
          var button = $('<input type="button" value="OK"/>');
          message.element.prepend(button);
          button.click(function(evt) {
            message.opacity = -0.5; // (less than zero, and not -1, so it will trigger deletion)
          });
        }
        messages.push(message);
      });
    }
  }
  displayMessage = function(text, error, duration) {
    displayMessages([[text, error ? "error" : "info", duration]]);
  }


  hideInfo = function() {
      var infoBox = $('#infopopup');
      var opacity;
      var fadeInfo = function() {
	  infoBox.css('opacity', opacity > 1 ? 1 : opacity);
	  opacity -= 0.05;
	  if (opacity <= 0) {
	      infoBox.css('display', 'none');
	      clearInterval(infoBoxTimer);
	      infoBoxTimer = 0;
	  }
      };
      return function(html, evt) {
	  opacity = 1;
	  infoBoxVisible = false;
	  if (!infoBoxTimer) {
	      infoBoxTimer = setInterval(fadeInfo, 10);
	  }
      };
  } ();

  Annotator.showSpinner = function(show) {
    if (show === undefined) {
      show = true;
    }
    var spinner = $('#spinner');
    spinner.css('display', show ? 'block' : 'none');
  }

  Annotator.actionsAllowed = (function() {
    var blind = $('#blind');
    var spinner = $('#spinner');
    var allowed = false;
    return function(_allowed) {
      if (_allowed === undefined) {
        return allowed;
      }
      blind.css('display', _allowed ? 'none' : 'block');
      if (_allowed) {
	  spinner.css('display', 'none');
      }
      return allowed = _allowed;
    }
  })();

  var hideAllForms = function() {
    displayMessages(false);
    annotator.keymap = {};
    if (formDisplayed) {
      $('input').blur();
      formDisplayed = false;
      keymap = {};
      $('#span_form').css('display', 'none');
      $('#arc_form').css('display', 'none');
      $('#auth_form').css('display', 'none');
      $('#import_form').css('display', 'none');
      fileBrowser.find('table.files tbody').html(''); // prevent a slowbug
      fileBrowser.css('display', 'none');
      Annotator.actionsAllowed(true);
      if (annotator.selectedRange) {
        var sel = document.getSelection();
        sel.removeAllRanges();
        sel.addRange(annotator.selectedRange);
      }
    }
  }

  var resizeFormToFit = function(form, typesContainer, html) {
    form.css('display', 'block');
    typesContainer.html('');
    var screenHeight = $(window).height() - formMargin;
    var emptyFormHeight = form.height();
    typesContainer.html(html);
    var fullFormHeight = form.height();
    var typesChildren = typesContainer.find('.type_scroller').css('max-height', 'inherit');
    var excessHeight = Math.max(0, fullFormHeight - screenHeight);
    var totalChildrenHeight = 0;
    var heights = typesChildren.map(function(childNo, child) {
        var height = $(child).height() - minFormElementHeight;
        totalChildrenHeight += height;
        return height;
    });
    typesChildren.each(function(childNo, child) {
        var maxHeight = minFormElementHeight + Math.max(0, heights[childNo] * (1 - excessHeight / totalChildrenHeight));
        $(child).css('max-height', maxHeight);
    });
    form.css('display', 'none');
  };

  var selectElement = function(table, element) {

  }
  var chooseDocument = function(evt) {
    var _doc = $(evt.target).closest('tr').data('value');
    $('#document_input').val(_doc);
    selectElementInTable($('#document_select'), _doc);
  }
  var chooseDocumentAndSubmit = function(evt) {
    chooseDocument(evt);
    fileBrowserSubmit();
  }
  var chooseDirectory = function(evt) {
    var _directory = $(evt.target).closest('tr').data('value');
    var real_directory = URLHash.current.directory;
    if (_directory == '..') {
      var pos = real_directory.lastIndexOf('/');
      real_directory = (pos == -1) ? '' : real_directory.substr(0, pos);
    } else if (real_directory == '') {
      real_directory = _directory;
    } else {
      real_directory += '/' + _directory;
    }
    $('#directory_input').val(real_directory);
    $('#document_input').val('');
    selectElementInTable($('#directory_select'), _directory);
  }
  var chooseDirectoryAndSubmit = function(evt) {
    chooseDirectory(evt);
    fileBrowserSubmit();
  }
  var filesData;
  var dirScroll;
  var fileScroll;

  var getDirectory = function(directory) {
    Annotator.showSpinner();
    $.ajax({
      url: ajaxBase,
      type: 'GET',
      data: { action: 'ls', directory: directory },
      success: function(response) {
        if (displayMessagesAndCheckForErrors(response)) {
          filesData = response;

          spanFormHTML = response.html;
          try {
	    resizeFormToFit(spanForm, $('#span_types'), spanFormHTML);
          }
	  catch(x) {
	    escaped = spanFormHTML.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
	    displayMessage("Error: failed to display span form; received HTML:<br/>"+escaped, "error", -1);
	    spanFormHTML = "<div><b>Error displaying form</b></div>";
	    resizeFormToFit(spanForm, $('#span_types'), spanFormHTML);
	  }
          annotator.spanKeymap = response.keymap;
	  // TODO: consider separating span and arc abbreviations
	  annotator.spanAbbreviations = response.abbrevs;
	  annotator.arcAbbreviations = response.abbrevs;
          spanForm.find('#span_types input:radio').click(spanFormSubmitRadio);
          spanForm.find('.collapser').click(collapseHandler);
          annotator.forceUpdateState = true;
        }
        if (!formDisplayed) {
          Annotator.actionsAllowed(true);
          Annotator.showSpinner(false);
        }
      },
      error: function(req, textStatus, errorThrown) {
        console.error("Directory fetch error", textStatus, errorThrown);
        $('#document_select').css('display', 'none');
        if (!formDisplayed) {
          Annotator.actionsAllowed(true);
          Annotator.showSpinner(false);
        }
      }
    });
  };

  var URLHash = function() {
    var original = window.location.hash;
    if (!original.length) {
      this.directory = '';
      this.doc = '';
      this.edited = [];
    } else {
      var pos = original.lastIndexOf('/');
      if (pos == -1) {
        pos = 0;
        this.directory = '';
      } else {
        this.directory = original.substring(1, pos);
      }
      this.edited = original.substr(pos + 1).split('--');
      this.doc = this.edited.shift();
    }

    this.toString = function(full) {
      if (full) {
        var docAndEdited = [this.doc];
        if (this.edited) docAndEdited.concat(this.edited);
        return '#' + this.directory + '/' + docAndEdited.join('--');
      } else {
        return this.directory + '/' + this.doc;
      }
    }
    this.engage = function() {
      window.location.hash = this.toString(true);
    }
    this.setDirectory = function(_directory, _doc, _edited) {
      this.directory = _directory;
      this.setDocument(_doc, _edited);
    }
    this.setDocument = function(_doc, _edited) {
      this.doc = _doc;
      this.setEdited(_edited);
    }
    this.setEdited = function(_edited) {
      if (!_edited) _edited = [];
      this.edited = _edited;
      this.engage();
    }
  }
  URLHash.current = {}; // all members undefined

  var selectElementInTable = function(table, value) {
    table.find('tr').removeClass('selected');
    if (value) {
      table.find('tr[data-value="' + value + '"]').addClass('selected');
    }
  }

  var updateFileBrowser = function() {
    var _directory = URLHash.current.directory;
    var _doc = URLHash.current.doc;

    $('#directory_input').val(_directory);
    $('#document_input').val(_doc);
    var pos = _directory.lastIndexOf('/');
    if (pos != -1) _directory = _directory.substring(pos + 1);
    selectElementInTable($('#directory_select'), _directory);
    selectElementInTable($('#document_select'), _doc);
  }

  var annotator = new Annotator('#svg', function() {
    var annotator = this;
    var PMIDre = new RegExp('^(?:PMID-?)?([0-9]{4,})');
    var PMCre  = new RegExp('^(?:PMC-?)?([0-9]{4,})');

    var saveUser;
    var savePassword;

    var normalize = function(str) {
      return str.toLowerCase().replace(' ', '_');
    }

    annotator.forceUpdateState = false;
    var showDir = false;
    var updateState = function(onRenderComplete) {
      if (!annotator.forceUpdateState && (annotator.drawing || lastHash == window.location.hash)) return;
      lastHash = window.location.hash;
      URLHash.last = URLHash.current;
      var urlHash = URLHash.current = new URLHash();

      $('#document_name').text(urlHash.toString());
      var _directory = urlHash.directory;
      var _doc = doc = urlHash.doc;
      if (_directory !== URLHash.last.directory) {
        getDirectory(_directory);
        showDir = !_doc;
        return;
      }
      if (urlHash.edited[0] == 'save') {
        renderAllToDisk();
        return;
      }
      annotator.edited = [urlHash.edited];
      updateFileBrowser();

      var PMIDm = PMIDre.exec(_doc);
      var PMCm  = PMCre.exec(_doc);
      if (PMIDm) {
        $('#original_link').attr("href","http://www.ncbi.nlm.nih.gov/pubmed/"+PMIDm[1]).css("display","inline");
      } else if (PMCm) {
        $('#original_link').attr("href","http://www.ncbi.nlm.nih.gov/pmc/articles/PMC"+PMCm[1]).css("display","inline");
      } else {
        $('#original_link').css("display","none");
      }

      Annotator.actionsAllowed(false);
      Annotator.showSpinner();
      if (!annotator.forceUpdateState && _doc === URLHash.last.doc && _directory === URLHash.last.directory) {
        $('title').text(_doc + ' - brat');
        // document unchanged, only edited changed - fetch not required
        annotator.renderData();
        if ($.isFunction(onRenderComplete)) {
          onRenderComplete.call(annotator, jsonData.error);
        }
        return;
      }
      annotator.forceUpdateState = false;
      if (!_doc) {
        if (showDir) {
          openFileBrowser();
        } else {
          Annotator.actionsAllowed(true);
          Annotator.showSpinner(false);
        }
        return;
      }
      $.ajax({
        url: ajaxBase,
        type: 'GET',
        data: { 'directory': _directory, 'document': _doc },
        success: function(jsonData) {
          if (!jsonData) {
            displayMessage('<strong>ERROR</strong><br/>No JSON data', true);
            annotator.clearSVG();
            Annotator.actionsAllowed(true);
            return;
          }
          displayMessagesAndCheckForErrors(jsonData);
          jsonData.document = _doc;
          annotator.renderData(jsonData);
          if ($.isFunction(onRenderComplete)) {
            onRenderComplete.call(annotator, jsonData.error);
          }
        },
        error: function(req, textStatus, errorThrown) {
          console.error("Document fetch error", textStatus, errorThrown);
          annotator.clearSVG();
          Annotator.actionsAllowed(true);
        },
      });
    };

    var renderDocument = function(_doc, onRenderComplete) {
      doc = _doc;
      new URLHash().setDocument(_doc);
    };

    annotator.postChangesAndReload = function() {
      var _doc = URLHash.current.doc;
      var _directory = URLHash.current.directory;
      $.extend(annotator.ajaxOptions, {
        directory: _directory,
        document: _doc,
      });
      Annotator.showSpinner();
      $.ajax({
        type: 'POST',
        url: ajaxBase,
        data: annotator.ajaxOptions,
        error: function(req, textStatus, errorThrown) {
          spinner.css('display', 'none');
          console.error("Change posting error", textStatus, errorThrown);
          Annotator.actionsAllowed(true);
        },
        success: function(response) {
          if (displayMessagesAndCheckForErrors(response)) {
            annotator.edited = response.edited;
            renderDocument(_doc);
            var newData = response.annotations;
            if (newData) {
              newData.document = _doc;
              annotator.renderData(newData);
            } else {
              displayMessage("No data received!", true); // TODO?
            }
          }
          Annotator.actionsAllowed(true);
          $('input').blur();
          formDisplayed = false;
        }
      });
      annotator.ajaxOptions = null;
    };

    annotator.renderSelected = function(evt, onRenderComplete) {
      doc = $('#document_select').val();
      renderDocument(doc, onRenderComplete);
      return false;
    };

    var renderToDiskAndSelectNext = function() {
      if (!annotator.user) return;
      annotator.renderSelected(null, function(error) {
        var svgMarkup = annotator.getSVG();
        var doc = annotator.getDocumentName();

        var nextFunction = function(data) {
          var select = $('#document_select')[0];
          select.selectedIndex = select.selectedIndex + 1;
          if (select.selectedIndex != -1) {
            setTimeout(renderToDiskAndSelectNext, 0);
          } else {
            alert('done');
          }
        };

        if (error) {
          nextFunction.call();
        } else {
          $.ajax({
            type: 'POST',
            url: ajaxBase,
            data: {
              action: 'save',
              directory: directory,
              document: doc,
              svg: svgMarkup,
            },
            error: function(req, textStatus, errorThrown) {
              console.error(doc, textStatus, errorThrown);
              alert('Error occured.\nSVG dump aborted.');
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

    $('#header').
        submit(annotator.renderSelected).
        children().
        removeAttr('disabled');

    $('#document_select').
        change(annotator.renderSelected);
    $('#directory_select').
        change(function(evt) {
          document.location.hash = $(evt.target).val();
        });

    var adjustToCursor = function(evt, element) {
      var screenHeight = $(window).height() - 15; // TODO HACK - no idea why -15 is needed
      var screenWidth = $(window).width();
      var elementHeight = element.height();
      var elementWidth = element.width();
      var y = Math.min(evt.clientY, screenHeight - elementHeight);
      var x = Math.min(evt.clientX, screenWidth - elementWidth);
      element.css({ top: y, left: x });
    };
    
    annotator.fillSpanTypesAndDisplayForm = function(evt, spanText, span) {
      Annotator.actionsAllowed(false);
      annotator.keymap = annotator.spanKeymap;
      $('#del_span_button').css('display', span ? 'inline' : 'none');
      $('#span_selected').text(spanText);
      var encodedText = encodeURIComponent(spanText);
      $('#span_uniprot').attr('href', 'http://www.uniprot.org/uniprot/?sort=score&query=' + encodedText);
      $('#span_entregene').attr('href', 'http://www.ncbi.nlm.nih.gov/gene?term=' + encodedText);
      $('#span_wikipedia').attr('href', 'http://en.wikipedia.org/wiki/Special:Search?search=' + encodedText);
      $('#span_google').attr('href', 'http://www.google.com/search?q=' + encodedText);
      $('#span_alc').attr('href', 'http://eow.alc.co.jp/' + encodedText);
      if (span) {
        $('#span_highlight_link').css('display', 'inline').attr('href', document.location + '/' + span.id);
        annotator.keymap[46] = 'del_span_button'; // Del
        var el = $('#span_' + normalize(span.type));
        if (el.length) {
          el[0].checked = true;
        } else {
          $('#span_form input:radio:checked').each(function (radioNo, radio) {
              radio.checked = false;
          });
        }
      } else {
        $('#span_highlight_link').css('display', 'none');
        annotator.keymap[46] = undefined;
        $('#span_form input:radio:first')[0].checked = true;
      }
      if (el = $('#span_mod_negation')[0]) {
        el.checked = span ? span.Negation : false;
      }
      if (el = $('#span_mod_speculation')[0]) {
        el.checked = span ? span.Speculation : false;
      }
      $('#span_form').css('display', 'block');
      $('#span_form input:submit').focus();
      formDisplayed = true;

      adjustToCursor(evt, spanForm);
    };
    $('#del_span_button').click(annotator.deleteSpan);

    var arcSubmit = function(type) {
      annotator.ajaxOptions.type = type;
      annotator.postChangesAndReload();
    }
    var arcFormSubmit = function(evt) {
      arcForm.css('display', 'none');
      annotator.keymap = {};
      var type = $('#arc_form input:radio:checked').val();
      if (type) { // (if not cancelled)
        arcSubmit(type);
      } else {
        displayMessage('Error: No type selected', true);
        hideAllForms();
      }
      return false;
    };
    var arcForm = $('#arc_form').
      submit(arcFormSubmit).
      bind('reset', hideAllForms);
    annotator.fillArcTypesAndDisplayForm = function(evt, originType, targetType, arcType, arcId) {
      Annotator.actionsAllowed(false);
      Annotator.showSpinner();
      $.ajax({
        url: ajaxBase,
        type: 'GET',
        data: {
          action: 'arctypes',
          directory: directory,
          origin: originType,
          target: targetType,
        },
        success: function(jsonData) {
	    Annotator.showSpinner(false);
            if (displayMessagesAndCheckForErrors(jsonData)) {
              if (jsonData.empty && !arcType) {
                // no valid choices
                displayMessage("No choices for "+originType+" -> "+targetType, true);
                Annotator.actionsAllowed(true);
              } else {
                resizeFormToFit(arcForm, $('#arc_roles'), jsonData.html);
                annotator.keymap = jsonData.keymap;
                if (arcId) {
                  $('#arc_highlight_link').css('display', 'inline').attr('href', document.location + '/' + arcId);
                  var el = $('#arc_' + normalize(arcType))[0];
                  if (el) {
                    el.checked = true;
                  }
                } else {
                  $('#arc_highlight_link').css('display', 'none');
                  el = $('#arc_form input:radio:first')[0];
                  if (el) {
                    el.checked = true;
                  }
                }
                var confirmMode = $('#confirm_mode')[0].checked;
                if (!confirmMode) {
                  arcForm.find('#arc_roles input:radio').click(arcFormSubmit);
                }
                $('#del_arc_button').css('display', arcType ? 'inline' : 'none');
                if (arcType) annotator.keymap[46] = 'del_arc_button'; // Del
                $('#arc_form').css('display', 'block');
                $('#arc_form input:submit').focus();
                formDisplayed = true;
                adjustToCursor(evt, arcForm);
              }
            } else {
                Annotator.actionsAllowed(true);
	    }
          },
        error: function(req, textStatus, errorThrown) {
          console.error("Arc type fetch error", textStatus, errorThrown);
          Annotator.actionsAllowed(true);
        },
      });
    };
    $('#del_arc_button').click(annotator.deleteArc);

    var authFormSubmit = function(evt) {
      var user = $('#auth_user').val();
      var password = $('#auth_pass').val();
      Annotator.showSpinner();
      $.ajax({
        type: 'POST',
        url: ajaxBase,
        data: {
          action: 'login',
          user: user,
          pass: password,
        },
        error: function(req, textStatus, errorThrown) {
          // TODO: check if it is the auth error
	  Annotator.showSpinner(false);
          authForm.css('display', 'block');
          $('#auth_user').select().focus();
          return false;
        },
        success: function(response) {
	  Annotator.showSpinner(false);
	  if (displayMessagesAndCheckForErrors(response)) {
	      annotator.user = response.user;
	      $('#auth_button').val('Logout');
	      $('#auth_user').val('');
	      $('#auth_pass').val('');
	  } else {
	      authForm.css('display', 'block');
	      $('#auth_user').select().focus();
	      return false;
	  }
        }
      });
      hideAllForms();
      return false;
    };
    var authForm = $('#auth_form').
      submit(authFormSubmit).
      bind('reset', hideAllForms);
    $('#auth_button').click(function() {
      var auth_button = $('#auth_button');
      if (auth_button.val() == 'Login') {
        $('#auth_form').css('display', 'block');
        $('#auth_user').select().focus();
        formDisplayed = true;
      } else {
	Annotator.showSpinner();
        $.ajax({
          type: 'POST',
          url: ajaxBase,
          data: {
            action: 'logout',
          },
          success: function(response) {
	    Annotator.showSpinner(false);
	    if (displayMessagesAndCheckForErrors(response)) {
		annotator.user = undefined;
		auth_button.val('Login');
	    }
          },
          error: function(req, textStatus, errorThrown) {
	    Annotator.showSpinner(false);
            console.error("Logout error", textStatus, errorThrown);
          },
        });
      }
    });

    updateState();
    setInterval(updateState, 200); // TODO okay?

    var resizeFunction = function(evt) {
      if (!annotator.drawing) {
        resizeFormToFit($('#span_form'), $('#span_types'), spanFormHTML);
        annotator.renderData();
      } else {
        annotator.redraw = true;
      }
    };

    var resizerTimeout = 0;
    $(window).resize(function(evt) {
        clearTimeout(resizerTimeout);
        resizerTimeout = setTimeout(resizeFunction, 100); // TODO is 100ms okay?
    });
  });

  var makeSortFunction = function(sort) {
    return function(a, b) {
        var col = sort[0];
        var aa = a[col];
        var bb = b[col];
        if (aa != bb) return (aa < bb) ? -sort[1] : sort[1];
        
        // prevent random shuffles on columns with duplicate values
        aa = a[0];
        bb = b[0];
        if (aa != bb) return (aa < bb) ? -1 : 1;
        return 0;
    };
  };
  var dirSort = [0, 1]; // column (0..), sort order (1, -1)
  var docSort = [0, 1];
  var dirSortFunction = makeSortFunction(dirSort);
  var docSortFunction = makeSortFunction(docSort);
  var openFileBrowser = function() {
    $('#file_browser').css('display', 'block');
    Annotator.actionsAllowed(false);
    formDisplayed = true;

    var html;
    var tbody;
    
    html = [];
    if (filesData.parent !== null) {
      html.push(
          '<tr data-value=".."><th>..</th></tr>'
          );
    }
    filesData.dirs.sort(dirSortFunction);
    $.each(filesData.dirs, function(dirNo, dir) {
      html.push(
        '<tr data-value="' + dir[0] + '"><th>' + dir[0] + '</th></tr>'
        );
    });
    html = html.join('');
    tbody = $('#directory_select tbody').html(html);
    $('#directory_select')[0].scrollTop = dirScroll;
    tbody.find('tr').
        click(chooseDirectory).
        dblclick(chooseDirectoryAndSubmit);

    html = [];
    filesData.docs.sort(docSortFunction);
    $.each(filesData.docs, function(docNo, doc) {
      html.push(
          '<tr data-value="' + doc[0] + '"><th>' + doc[0] + '</th><td>' + Annotator.formatTime(doc[1]*1000) + '</td></tr>'
          );
    });
    html = html.join('');
    tbody = $('#document_select tbody').html(html);
    $('#document_select')[0].scrollTop = fileScroll;
    tbody.find('tr').
        click(chooseDocument).
        dblclick(chooseDocumentAndSubmit);

    updateFileBrowser();
    $('#document_input').focus().select();
  }
  $('#file_browser_button').click(openFileBrowser);

  var openImportForm = function() {
      $('#import_docid')[0].value = '';
      $('#import_title')[0].value = '';
      $('#import_text')[0].value = '';

      $('#import_form').css('display', 'block');
      Annotator.actionsAllowed(false);
      formDisplayed = true;
  }
  $('#import_button').click(openImportForm);
  var importFormSubmit = function(evt) {
      $('#import_form').css('display', 'none');
      var docid = $('#import_docid')[0].value;
      var doctitle = $('#import_title')[0].value;
      var doctext = $('#import_text')[0].value;
      displayMessage("Directory:"+directory);
      displayMessage("Import:<br/>Document ID: <b>"+docid+"</b><br/>TITLE:<b>"+doctitle+"</b><br/>TEXT:<br/>"+doctext, 0, -1);
      Annotator.actionsAllowed(true);
      formDisplayed = false;
      return false;
  };
  var importForm = $('#import_form').
      submit(importFormSubmit).
      bind('reset', hideAllForms);

  $(document).keydown(function(evt) {    
    var mapping;
    var code = evt.keyCode;
    if (code == 27) { // ("Esc")
      hideAllForms();
      return false;
    } else if (!formDisplayed && code == 37) { // Left arrow
      var pos;
      var curDoc = URLHash.current.doc;
      // could have used $.inArray, but this way is extensible
      $.each(filesData.docs, function(docNo, doc) {
        if (doc[0] == curDoc) {
          pos = docNo;
          return false;
        }
      });
      if (pos > 0) {
        new URLHash().setDocument(filesData.docs[pos - 1][0]);
      }
      return false;
    } else if (!formDisplayed && code == 39) { // Right arrow
      var pos;
      var curDoc = URLHash.current.doc;
      // could have used $.inArray, but this way is extensible
      $.each(filesData.docs, function(docNo, doc) {
        if (doc[0] == curDoc) {
          pos = docNo;
          return false;
        }
      });
      if (pos < filesData.docs.length - 1) {
        new URLHash().setDocument(filesData.docs[pos + 1][0]);
      }
      return false;
    } else if (mapping = annotator.keymap[code] ||
        annotator.keymap[String.fromCharCode(code)]) {
      var el = $('#' + mapping);
      if (el.length) el[0].click();
    } else if (!formDisplayed && code == 9) { // Tab
      openFileBrowser();
      return false;
    }
  });

  // user
  Annotator.showSpinner();
  $.ajax({
    type: 'POST',
    url: ajaxBase,
    data: {
      action: 'getuser',
    },
    success: function(jsonData) {
      var auth_button = $('#auth_button');
      if (jsonData.user) {
        annotator.user = jsonData.user;
        //displayMessage('Hello, ' + jsonData.user);
        auth_button.val('Logout');
      } else {
        auth_button.val('Login');
      }
    },
    error: function(req, textStatus, errorThrown) {
      console.error("User fetch error", textStatus, errorThrown);
    },
  });

  var collapseHandler = function(evt) {
    var el = $(evt.target);
    var open = el.hasClass('open');
    var collapsible = el.parent().find('.collapsible').first();
    el.toggleClass('open');
    collapsible.toggleClass('open');
  };
  var fileBrowserSubmit = function(evt) {
    var _directory = $('#directory_input').val();
    var _doc = $('#document_input').val();
    new URLHash().setDirectory(_directory, _doc);
    Annotator.actionsAllowed(true); // just in case the user opens current doc
    dirScroll = $('#directory_select')[0].scrollTop;
    fileScroll = $('#document_select')[0].scrollTop;
    fileBrowser.find('table.files tbody').html(''); // prevent a slowbug
    fileBrowser.css('display', 'none');
    formDisplayed = false;
    return false;
  };
  foo = URLHash;
  var fileBrowser = $('#file_browser').
    submit(fileBrowserSubmit).
    bind('reset', hideAllForms);
  var makeSortFunction = function(sort, th, thNo) {
      $(th).click(function() {
          if (sort[0] == thNo) sort[1] = -sort[1];
          else { sort[0] = thNo; sort[1] = 1; }
          openFileBrowser(); // resort
      });
  }
  $('#directory_select thead tr *').each(function(thNo, th) {
      makeSortFunction(dirSort, th, thNo);
  });
  $('#document_select thead tr *').each(function(thNo, th) {
      makeSortFunction(docSort, th, thNo);
  });
  var spanFormSubmit = function(evt) {
    spanForm.css('display', 'none');
    annotator.keymap = {};
    var type = $('#span_form input:radio:checked').val();
    if (type) {
      annotator.ajaxOptions.type = type;
      var el;
      if (el = $('#span_mod_negation')[0]) {
        annotator.ajaxOptions.negation = el.checked;
      }
      if (el = $('#span_mod_speculation')[0]) {
        annotator.ajaxOptions.speculation = el.checked;
      }
      annotator.postChangesAndReload();
    } else {
      hideAllForms();
      displayMessage('Error: No type selected', true);
    }
    return false;
  };
  var spanFormSubmitRadio = function(evt) {
    var confirmMode = $('#confirm_mode')[0].checked;
    if (confirmMode) {
      $('#span_form input:submit').focus();
    } else {
      spanFormSubmit(evt);
    }
  }
  var spanForm = $('#span_form').
    submit(spanFormSubmit).
    bind('reset', hideAllForms);
});
