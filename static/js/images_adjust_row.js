var margin_left = 7;
var pixel_adjust = 16;
var max_height = 300;

function get_scaled_width(image) {
    let real_w = image.getAttribute("image_width");
    let real_h = image.getAttribute("image_height");
    let asp = real_w / real_h;
    let w = max_height * asp;
    return w;
}

function adjust_stack(stack, current_w, max_width) {
    let asp = current_w / max_width;
    for (let image of stack) {
        image.height = (max_height / asp).toFixed() - pixel_adjust;
        removeClass(image, "hidden");
    }
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

        if (w > max_width && stack.length > 0) {
            console.log("------------- Width overflow " + count + " ----------------");
            stack.push(image);
            adjust_stack(stack, w, max_width);

            w = 0
            stack = []
            continue
        }
        stack.push(image);
        w += margin_left
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