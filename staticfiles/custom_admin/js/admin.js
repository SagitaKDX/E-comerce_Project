// Admin Dashboard Scripts
document.addEventListener('DOMContentLoaded', function() {
    // Toggle sidebar on small screens
    const toggleSidebarBtn = document.getElementById('sidebarToggleTop');
    if (toggleSidebarBtn) {
        toggleSidebarBtn.addEventListener('click', function() {
            document.body.classList.toggle('sidebar-toggled');
            document.querySelector('.sidebar').classList.toggle('toggled');
        });
    }
    
    // Close any open menu dropdowns when window is resized
    window.addEventListener('resize', function() {
        const vw = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
        if (vw < 768) {
            document.querySelector('.sidebar').classList.add('toggled');
        } else {
            document.querySelector('.sidebar').classList.remove('toggled');
        }
    });
    
    // Auto-hide alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });
    
    // Image preview for product forms
    const imageInput = document.querySelector('input[type="file"]');
    if (imageInput) {
        imageInput.addEventListener('change', function() {
            const file = this.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    const preview = document.querySelector('.img-thumbnail');
                    if (preview) {
                        preview.src = e.target.result;
                    } else {
                        const img = document.createElement('img');
                        img.src = e.target.result;
                        img.classList.add('img-thumbnail', 'mt-2');
                        img.style.maxHeight = '200px';
                        imageInput.parentNode.appendChild(img);
                    }
                };
                reader.readAsDataURL(file);
            }
        });
    }
});
