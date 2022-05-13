var username = document.getElementById('user_posts').value;
var current_username = document.getElementById('current_user').value;

function set_media_private(media_id, checked) {
    if (checked)
        fetch('/api/media/posts/' + media_id + '/set/private')
    else
        fetch('/api/media/posts/' + media_id + '/set/public')
}

fetch('/api/media/stream/' + username)
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

        let count = 0;
        for (media of data.media_files) {
            count += 1;
            let private = (media.is_public ? "" : "checked")
            let verbose_date = second_get_verbose_date(data.timestamp - media.creation_date);

            html += ` <div class="col-lg-3 col-md-12 mb-3 media-container"> `;

            if (media.file_format == ".MP4") {
                html += `
                <div class="bg-image hover-overlay ripple shadow-1-strong rounded">
                    <video class='video_player' width="100%" height="300" loop="true" preload="none" poster="/api/media/get/${media.media_id}.300.PNG" id="video_${ count++ }" allowfullscreen="">
                        <source src="/api/media/get/${media.media_id}" type="video/mp4">
                        Sorry, your browser doesn't support embedded videos.
                    </video>
                </div>
                `;

            } else {

                html += `
                    <div class="bg-image hover-overlay ripple shadow-1-strong rounded">
                        <a href='/media/edit/${media.media_id}'>
                            <img src='/api/media/get/${media.media_id}' class="img-fluid img-fit-inside img-small-display">
                                <div class="mask" style="background-color: rgba(57, 192, 237, 0.2)"></div>
                        </a>
                    </div>
                `;
            }

            if (media.username == current_username)
                html += `
                    <span class='text-white'>
                        <small>
                            <div class='pull-right'><button class='btn_delete' api_call='/api/media/remove/${media.media_id}'>Delete <i class='fa fa-lg fa-times'></i></button></div>
                            <span class=''> ${ verbose_date } &nbsp;&nbsp;</span>
                            <span class="">
                                <i class='fa fa-lock'></i>
                                <label class="form-check-label" >Private</label>
                                <input class="form-check-input checkbox_private" type="checkbox" value="" ${private} media_id='${media.media_id}'/>
                            </span>
                        </small>
                    </span>
                `;

            html += `</div>`;
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

        var api_video = document.getElementsByClassName('video_player');
        for (video of api_video) {
            video.addEventListener('click', function(evt) {
                video.play();
                video.setAttribute("controls", "");
            })
        }

        var api_delete_files = document.getElementsByClassName('btn_delete');
        for (btn_delete of api_delete_files) {
            btn_delete.addEventListener('click', function(evt) {
                var url = this.getAttribute("api_call");
                var obj = this;
                fetch(url)
                    .then(response => response.json())
                    .then(data => {
                        if (data.status != "success") {
                            document.getElementById('system_message').innerHTML = " Could not download the files list for user " + username;
                            return
                        } else {
                            let media_view = findParentClass(obj, "media-container")
                            addClass(media_view, "hidden")
                        }
                    })
                    .catch(error => {
                        document.getElementById('system_message').innerHTML = " Failed " + error;
                        throw (error);
                    })
            })
        }
    });