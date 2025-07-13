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

function showToast(title, text, icon = 'success') {
    Toast.fire({
      icon,    // success / error / warning / info / question
      title,
      text     // 可不傳，用於補充說明
    });
  }