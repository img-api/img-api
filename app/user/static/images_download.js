var username = document.getElementById('user_posts').value;
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
            <div class="col-lg-4 col-md-12 mb-4">
                <div class="bg-image hover-overlay ripple shadow-1-strong rounded">
                <a href='/media/edit/${media.media_id}'>
                    <img src='/api/media/get/${media.media_id}' class="img-fluid img-fit-inside">
                        <div class="mask" style="background-color: rgba(57, 192, 237, 0.2)"></div>
                </a>
                </div>
            `

            if (media.username == username)
                html += `
                <span class='text-white'>
                    <div class="">
                        <i class='fa fa-lock'></i>
                        <label class="form-check-label" for="flexCheckChecked">Private</label>
                        <input class="form-check-input" type="checkbox" value="" id="flexCheckChecked" ${private}/>
                    </div>
                </span>
            `

            html += `
            </div>
            `;
        }

        media_container.innerHTML = html
    });