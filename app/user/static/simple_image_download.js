var username = document.getElementById('user_posts').value;
var media_id = document.getElementById('media_id').value;
fetch('/api/media/get/' + media_id)
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
            if (media.file_format == ".MP4") {
                html += `
                <div class="col-lg-4 col-md-12 mb-4">
                    <video controls="" width="80%" loop="true" preload="none" poster="'/api/media/edit/${media.media_id}'.thumb.jpg" id="video_${ count++ }" allowfullscreen="">
                        <source src="'/api/media/edit/${media.media_id}'" type="video/mp4">
                        Sorry, your browser doesn't support embedded videos.
                    </video>
                </div>
                `;

            } else {
                html += `
                    <div class="col-lg-4 col-md-12 mb-4">
                        <div class="bg-image hover-overlay ripple shadow-1-strong rounded">
                        <a href='/api/media/edit/${media.media_id}'>
                            <img src='/api/media/get/${media.media_id}' class="img-fluid img-fit-inside">
                                <div class="mask" style="background-color: rgba(57, 192, 237, 0.2)"></div>
                        </a>
                        </div>
                    </div>
                `;
            }
        }

        media_container.innerHTML = html
    });