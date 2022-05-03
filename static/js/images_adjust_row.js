var margin_right = 7;
var max_height = 300;

function get_scaled_width(image) {
    let real_w = image.getAttribute("image_width");
    let real_h = image.getAttribute("image_height");
    let asp = real_w / real_h;
    let w = max_height * asp;
    return w;
}

function adjust_stack(stack, current_w, max_width) {

    let asp = 0;

    if (stack.length == 1)
        asp = current_w / max_width;
    else
        asp = current_w / (max_width - margin_right * (stack.length - 1));

    let final_w = 0;
    let count = 0;
    for (let image of stack) {
        image.height = (max_height / asp);

        if (stack.length == 1)  {
            if (image.height < max_height) {
                console.log(" Underflow ")
            }
        }

        removeClass(image, "hidden");
        final_w += image.width + margin_right;

        count += 1;

        let gallery = findParentClass(image, "img_gallery")
        if (stack.length > 1 && count == stack.length && count != 1) {
            addClass(gallery, "pull-right")
        } else {
            removeClass(gallery, "pull-right")
        }

    }

    console.log("Final width after adjust " + final_w + "  LOST " + (max_width - final_w))
}

function adjust_images_to_row() {
    var main_row = document.getElementById('main_row');
    console.log("MAX WIDTH " + main_row.clientWidth);

    let max_width = main_row.clientWidth;
    var images = document.getElementsByClassName('img-row');

    let w = 0;
    let stack = [];

    for (let image of images) {

        let count = image.getAttribute("image_count");
        let image_w = get_scaled_width(image);

        w += image_w;
        console.log(" " + image.getAttribute("image_count") + ` (${ image_w } => ${ w }) `)

        //if (count > 5) return;

        if (w > max_width) { //  && stack.length > 0
            console.log("------------- Width overflow " + count + " ----------------");
            stack.push(image);
            adjust_stack(stack, w, max_width);

            w = 0
            stack = []
            continue
        }

        if (stack.length > 1)
            w += margin_right

        stack.push(image);
    }
}

window.addEventListener('load', function() {
    console.log('All assets are loaded')
    adjust_images_to_row()
})

window.addEventListener('resize', function(event) {
    console.log('Readjust')
    adjust_images_to_row()
}, true);