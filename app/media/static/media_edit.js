var api_btn_process = document.getElementsByClassName('api_btn_process');
var media_id = document.getElementById('media_id').value;

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
                    alert("TRANSFORMATION FAILED " + data.error_msg);
                }

                if (data.job_status == "finished") {
                    // Cancel my interval
                    clearInterval(intervals[job_id]);

                    let api_get = "/api/transform/get/" + job_id;
                    let img = document.getElementById('img_edit_image');
                    img.src = api_get
                }
            })
            .catch((error) => {
                alert("INTERNAL SERVER ERROR");
            });

    }, 1000, job_id);

    intervals[job_id] = job_monitoring_interval
}

for (btn of api_btn_process) {
    btn.addEventListener('click', function(evt) {
        let process = this.getAttribute('process')
        let api_url = '/api/transform/' + process + '/' + media_id;

        console.log(" Backend perform operation " + process)
        fetch(api_url, {
                method: 'post',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    "media_id": this.value,
                    "process": process
                }),
            })
            .then(response => response.json())
            .then(data => {
                if (data.status != "success") {
                    alert("TRANSFORMATION FAILED " + data.error_msg);
                }

                console.log(" Loaded, now we have to monitor " + data.job_id)
                job_monitoring(data.job_id);
            })
            .catch((error) => {
                debugger;
                alert("INTERNAL SERVER ERROR");
                console.log(" INTERNAL SERVER ERROR ");
            });
    })
}