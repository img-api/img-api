function getUrlParameter(name) {
    name = name.replace(/[\[]/, '\\[').replace(/[\]]/, '\\]');
    let regex = new RegExp('[\\?&]' + name + '=([^&#]*)');
    let results = regex.exec(location.search);
    return results === null ? '' : decodeURIComponent(results[1].replace(/\+/g, ' '));
}


// This function returns a short date or time in hours verbose
function second_get_verbose_date(seconds, max_day = 15) {
    if (seconds < 0) {
        return "now";
    }

    let d = Math.floor(seconds / (60 * 60 * 24));
    if (d > max_day)
        return new Date(seconds * 1000);

    if (d == 1)
        return "1 day ago";

    if (d > 1)
        return d + " days ago";

    let h = Math.floor(seconds / (60 * 60));
    let m = Math.floor(seconds / (60));

    if (h == 1)
        return "1 hour ago";

    if (h > 1)
        return h + " hours ago";

    if (m < 5)
        return "a moment ago";

    if (m == 0)
        return "now";

    return m + " minutes ago";
}

function hasClass(ele, cls) {
    //console.log(ele.className);
    return !!ele.className.match(new RegExp('(\\s|^)' + cls + '(\\s|$)'));
}

function addClass(ele, cls) {
    if (!hasClass(ele, cls)) ele.className += " " + cls;
}

function removeClass(ele, cls) {
    if (hasClass(ele, cls)) {
        var reg = new RegExp('(\\s|^)' + cls + '(\\s|$)');
        ele.className = ele.className.replace(reg, ' ');
    }
}

function findParentClass(element, class_search) {
    while (element && !hasClass(element,class_search)) {
        element = element.parentNode;
    };

    return element;
}