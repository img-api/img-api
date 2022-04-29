var input_request = document.getElementById("user_media_upload_request_url");

var job_monitoring_interval = null;
var intervals = {};

function job_monitoring(job_id) {
    if (job_monitoring_interval)
        clearInterval(job_monitoring_interval);

    job_monitoring_interval = setInterval(function(job_id) {
        let api_url = "/api/transform/job/" + job_id;
        fetch(api_url)
            .then(response => response.json())
            .then(data => {
                if (data.status != "success") {
                    clearInterval(intervals[job_id]);
                    input_request.placeholder = "There was a problem loading this URL"
                    return
                }

                if (data.job_status == "finished") {
                    clearInterval(intervals[job_id]);

                    if (data.result.state == "error") {
                        input_request.placeholder = "There was a problem loading this image. Please try a different one..."
                        return
                    }

                    input_request.placeholder = "Done"
                }
            })
            .catch((error) => {
                //alert("INTERNAL SERVER ERROR");
            });

        if (input_request.placeholder == "") {
            input_request.placeholder = "Loading..."
        } else {
            input_request.placeholder = ""
        }

    }, 1000, job_id);

    intervals[job_id] = job_monitoring_interval
}

input_request.addEventListener('change', function(evt) {
    console.log(" Backend get URL " + this.value)

    var fetch_url = this.value
    this.value = ""
    this.placeholder = "loading..."

    fetch('/api/media/fetch', {
            method: 'post',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                "request_url": fetch_url
            }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.status != "success") {
                alert("FETCH " + data.error_msg);
                return
            }

            job_monitoring(data.job_id);
        })
        .catch((error) => {
            debugger;
            alert("INTERNAL SERVER ERROR");
        });
})