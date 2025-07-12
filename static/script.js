function showLoading(title, text) {
    Swal.fire({
        title: title,
        text: text,
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });
}

function closeLoading() {
    Swal.close();
}