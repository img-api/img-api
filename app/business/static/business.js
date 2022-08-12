var btn_create = document.getElementById("btn_biz_create");
if (btn_create) {
    btn_create.addEventListener("click", function(e) {
        biz_name = document.getElementById("biz_name").value;
        biz_email = document.getElementById("biz_email").value;

        main_address_1 = document.getElementById("biz_main_address").value;
        main_address_2 = document.getElementById("biz_main_address_2").value;

        phone_number = document.getElementById("biz_phone_number").value;

        fetch('/api/biz/create', {
                method: 'post',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    "name": biz_name,
                    "email": biz_email,
                    "main_address": main_address_1,
                    "main_address_1": main_address_2,
                    "phone_number": phone_number
                }),
            })
            .then(response => response.json())
            .then(data => {
                if (data.status != "success") {
                    debugger;
                    alert(data.error_msg);
                    return;
                }
                window.location.href = '/business/';
            })
            .catch((error) => {
                debugger;
                alert("INTERNAL SERVER ERROR");
            });

    }, false);
}

