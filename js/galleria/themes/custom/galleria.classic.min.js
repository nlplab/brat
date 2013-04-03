/*
 Galleria Classic Theme 2011-08-01
 http://galleria.aino.se

 Copyright (c) 2011, Aino
 Licensed under the MIT license.
*/
Galleria.requires(1.25,"This version of Classic theme requires Galleria 1.2.5 or later");
(function(b){Galleria.addTheme({name:"classic",author:"Galleria",css:"galleria.classic.css",defaults:{transition:"slide",thumbCrop:"height",_toggleInfo:!0},init:function(e){this.addElement("info-link","info-close");this.append({info:["info-link","info-close"]});var c=this.$("info-link,info-close,info-text"),d=Galleria.TOUCH,f=d?"touchstart":"click";this.$("loader,counter").show().css("opacity",0.4);d||(this.addIdleState(this.get("image-nav-left"),{left:-50}),this.addIdleState(this.get("image-nav-right"),
{right:-50}),this.addIdleState(this.get("counter"),{opacity:0}));e._toggleInfo===!0?c.bind(f,function(){c.toggle()}):(c.show(),this.$("info-link, info-close").hide());this.bind("thumbnail",function(a){d?b(a.thumbTarget).css("opacity",this.getIndex()?1:0.6):(b(a.thumbTarget).css("opacity",0.6).parent().hover(function(){b(this).not(".active").children().stop().fadeTo(100,1)},function(){b(this).not(".active").children().stop().fadeTo(400,0.6)}),a.index===this.getIndex()&&b(a.thumbTarget).css("opacity",
1))});this.bind("loadstart",function(a){a.cached||this.$("loader").show().fadeTo(200,0.4);this.$("info").toggle(this.hasInfo());b(a.thumbTarget).css("opacity",1).parent().siblings().children().css("opacity",0.6)});this.bind("loadfinish",function(){this.$("loader").fadeOut(200)})}})})(jQuery);
