var btn_login = document.getElementById("btn_login");
if (btn_login) {
    btn_login.addEventListener("click", function(e) {

        email = document.getElementById("email").value;
        password = document.getElementById("password").value;

        fetch('/api/user/login', {
                method: 'post',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    "email": email,
                    "password": password
                }),
            })
            .then(response => response.json())
            .then(data => {
                if (data.status != "success") {
                    debugger;
                    alert(data.error_msg);
                    return;
                }
                window.location.href = '/';
            })
            .catch((error) => {
                debugger;
                alert("INTERNAL SERVER ERROR");
            });

    }, false);

    document.getElementById("email").focus();

    // Just login on password enter.
    document.getElementById("password").onkeyup = function(e) {
        if (e.which == 13) btn_login.click();
    };
}

var btn_create_account = document.getElementById("btn_create_account");
if (btn_create_account) {
    btn_create_account.addEventListener("click", function(e) {
        first_name = document.getElementById("first_name").value;
        last_name = document.getElementById("last_name").value;

        username = document.getElementById("username").value;
        email = document.getElementById("email").value;
        password = document.getElementById("password").value;

        if (!username || !email || !password) {
            alert(' Please check that all the fields are completed ');
            return
        }

        fetch('/api/user/create', {
                method: 'post',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    "email": email,
                    "password": password,
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name,
                }),
            })
            .then(response => response.json())
            .then(data => {
                if (data.status != "success") {
                    alert("LOGIN " + data.error_msg);
                    return;
                }

                window.location.href = "/login?email=" + encodeURIComponent(email)
            })

            .catch((error) => {
                debugger;
                alert("INTERNAL SERVER ERROR");
            });

    }, false);
}

email = getUrlParameter('email');
if (email) {
    document.getElementById("email").value = email;
    document.getElementById("password").focus();
}