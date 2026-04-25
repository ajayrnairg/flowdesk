/**
 * FLOWDESK BOOKMARKLET
 * 
 * Copy the minified code below and create a new bookmark in your browser.
 * Paste the code into the 'URL' or 'Location' field.
 */

/* Raw Code: */
(function(){
    var u = window.location.href,
        t = document.title,
        h = window.location.hostname,
        s = window.getSelection().toString().trim(),
        c = "article";
    
    if (h.includes("youtube.com") || h.includes("youtu.be")) c = "youtube";
    else if (h.includes("github.com")) c = "github";
    else if (h.includes("twitter.com") || h.includes("x.com")) c = "twitter";
    else if (h.includes("linkedin.com")) c = "linkedin";

    if ((c === "twitter" || c === "linkedin") && !s) {
        alert("Please select the post text first, then click FlowDesk Save.");
        return;
    }
    
    var url = "https://flowdesk-sand.vercel.app/save?url=" + encodeURIComponent(u) + 
              "&title=" + encodeURIComponent(t) + 
              "&text=" + encodeURIComponent(s) + 
              "&type=" + c;
              
    window.open(url, "_blank");
})();

/* Minified (Copy this one): */
javascript:(function(){var u=window.location.href,t=document.title,h=window.location.hostname,s=window.getSelection().toString().trim(),c="article";if(h.includes("youtube.com")||h.includes("youtu.be"))c="youtube";else if(h.includes("github.com"))c="github";else if(h.includes("twitter.com")||h.includes("x.com"))c="twitter";else if(h.includes("linkedin.com"))c="linkedin";if((c==="twitter"||c==="linkedin")&&!s){alert("Please select the post text first, then click FlowDesk Save.");return;}var url="https://flowdesk-sand.vercel.app/save?url="+encodeURIComponent(u)+"&title="+encodeURIComponent(t)+"&text="+encodeURIComponent(s)+"&type="+c;window.open(url,"_blank");})();
