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