var api_btn_process = document.getElementsByClassName('api_btn_process');
var media_id = document.getElementById('media_id').value;

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
            })
            .catch((error) => {
                debugger;
                //alert("INTERNAL SERVER ERROR");
                console.log(" INTERNAL SERVER ERROR ");
            });
    })
}