var input_request = document.getElementById("user_media_upload_request_url");

input_request.addEventListener('change', function(evt) {
    console.log(" Backend get URL " + this.value)

    fetch('/api/media/fetch', {
            method: 'post',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                "request_url": this.value
            }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.status != "success") {
                alert("FETCH " + data.error_msg);
            }

        })
        .catch((error) => {
            debugger;
            alert("INTERNAL SERVER ERROR");
        });
})