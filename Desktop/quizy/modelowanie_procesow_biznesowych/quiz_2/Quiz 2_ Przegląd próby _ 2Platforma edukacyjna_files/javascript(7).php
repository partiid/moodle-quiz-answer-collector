var scrolltotop={setting:{startline:100,scrollto:0,scrollduration:1000,fadeduration:[500,100]},controlHTML:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><path fill="#FFFFFF" d="M201.4 137.4c12.5-12.5 32.8-12.5 45.3 0l160 160c12.5 12.5 12.5 32.8 0 45.3s-32.8 12.5-45.3 0L224 205.3 86.6 342.6c-12.5 12.5-32.8 12.5-45.3 0s-12.5-32.8 0-45.3l160-160z"/></svg>',controlattrs:{offsetx:5,offsety:5},anchorkeyword:'#top',state:{isvisible:!1,shouldvisible:!1},scrollup:function(){if(!this.cssfixedsupport)
this.$control.css({opacity:0})
var dest=isNaN(this.setting.scrollto)?this.setting.scrollto:parseInt(this.setting.scrollto)
if(typeof dest=="string"&&jQuery('#'+dest).length==1)
dest=jQuery('#'+dest).offset().top
else dest=0
this.$body.animate({scrollTop:dest},this.setting.scrollduration)},keepfixed:function(){var $window=jQuery(window)
var controlx=$window.scrollLeft()+$window.width()-this.$control.width()-this.controlattrs.offsetx
var controly=$window.scrollTop()+$window.height()-this.$control.height()-this.controlattrs.offsety
this.$control.css({left:controlx+'px',top:controly+'px'})},togglecontrol:function(){var scrolltop=jQuery(window).scrollTop()
if(!this.cssfixedsupport)
this.keepfixed()
this.state.shouldvisible=(scrolltop>=this.setting.startline)?!0:!1
if(this.state.shouldvisible&&!this.state.isvisible){this.$control.stop().animate({opacity:1},this.setting.fadeduration[0])
this.state.isvisible=!0}else if(this.state.shouldvisible==!1&&this.state.isvisible){this.$control.stop().animate({opacity:0},this.setting.fadeduration[1])
this.state.isvisible=!1}},init:function(){jQuery(document).ready(function($){var mainobj=scrolltotop
var iebrws=document.all
mainobj.cssfixedsupport=!iebrws||iebrws&&document.compatMode=="CSS1Compat"&&window.XMLHttpRequest
mainobj.$body=(window.opera)?(document.compatMode=="CSS1Compat"?$('html'):$('body')):$('html,body')
mainobj.$control=$('<div id="topcontrol">'+mainobj.controlHTML+'</div>').css({position:mainobj.cssfixedsupport?'fixed':'absolute',bottom:mainobj.controlattrs.offsety,right:mainobj.controlattrs.offsetx,opacity:0,cursor:'pointer'}).attr({title:'Scroll Back to Top'}).click(function(){mainobj.scrollup();return!1}).appendTo('body')
if(document.all&&!window.XMLHttpRequest&&mainobj.$control.text()!='')
mainobj.$control.css({width:mainobj.$control.width()})
mainobj.togglecontrol()
$('a[href="'+mainobj.anchorkeyword+'"]').click(function(){mainobj.scrollup()
return!1})
$(window).bind('scroll resize',function(e){mainobj.togglecontrol()})})}}
scrolltotop.init()