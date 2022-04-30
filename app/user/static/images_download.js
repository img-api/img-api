var username = document.getElementById('user_posts').value;
var current_username = document.getElementById('current_user').value;

function set_media_private(media_id, checked) {
    if (checked)
        fetch('/api/media/posts/' + media_id + '/set/private')
    else
        fetch('/api/media/posts/' + media_id + '/set/public')
}

fetch('/api/media/posts/' + username)
    .then(response => response.json())
    .then(data => {

        let m = document.getElementById('system_message');
        if (data.media_files.length == 0) {
            m.innerHTML = " Could not download the files list for user " + username;
            return
        }

        m.innerHTML = "";

        let media_container = document.getElementById('media_posts_container');
        let html = "";

        for (media of data.media_files) {
            let private = (media.is_public ? "" : "checked")

            html += `
            <div class="col-lg-2 col-md-12 mb-2">
                <div class="bg-image hover-overlay ripple shadow-1-strong rounded">
                <a href='/media/edit/${media.media_id}'>
                    <img src='/api/media/get/${media.media_id}' class="img-fluid img-fit-inside">
                        <div class="mask" style="background-color: rgba(57, 192, 237, 0.2)"></div>
                </a>
                </div>
            `

            if (media.username == current_username)
                html += `
                <span class='text-white'>
                    <div class="">
                        <i class='fa fa-lock'></i>
                        <label class="form-check-label" >Private</label>
                        <input class="form-check-input checkbox_private" type="checkbox" value="" ${private} media_id='${media.media_id}'/>
                    </div>
                </span>
            `

            html += `
            </div>
            `;
        }

        media_container.innerHTML = html

        var api_checkbox_private = document.getElementsByClassName('checkbox_private');
        for (checkbox of api_checkbox_private) {
            checkbox.addEventListener('change', function(evt) {
                if (this.checked == false) {
                    console.log("PUBLIC");
                    set_media_private(this.attributes.media_id.value, false)
                } else {
                    console.log("PRIVATE");
                    set_media_private(this.attributes.media_id.value, true)
                }
            })
        }
    });