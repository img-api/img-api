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

        for (media of data.media_files) {
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

        media_container.innerHTML = html
    });