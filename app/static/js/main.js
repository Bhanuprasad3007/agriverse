// Show loading spinner during AJAX requests
$(document).ajaxStart(function() {
    showSpinner();
}).ajaxStop(function() {
    hideSpinner();
});

function showSpinner() {
    const spinner = `
        <div class="spinner-overlay">
            <div class="spinner-border" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>
    `;
    $('body').append(spinner);
}

function hideSpinner() {
    $('.spinner-overlay').remove();
}

// Initialize tooltips
$(function () {
    $('[data-bs-toggle="tooltip"]').tooltip();
});

// Initialize popovers
$(function () {
    $('[data-bs-toggle="popover"]').popover();
});

// Auto-hide alerts after 5 seconds
$(document).ready(function() {
    setTimeout(function() {
        $('.alert').fadeOut('slow');
    }, 5000);
});

// Form validation
function validateForm(formId) {
    const form = document.getElementById(formId);
    if (!form.checkValidity()) {
        event.preventDefault();
        event.stopPropagation();
    }
    form.classList.add('was-validated');
}

// File upload preview
function previewImage(input, previewId) {
    if (input.files && input.files[0]) {
        const reader = new FileReader();
        reader.onload = function(e) {
            $(`#${previewId}`).attr('src', e.target.result);
        }
        reader.readAsDataURL(input.files[0]);
    }
}

// Format currency
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    }).format(amount);
}

// Format date
function formatDate(dateString) {
    const options = { year: 'numeric', month: 'long', day: 'numeric' };
    return new Date(dateString).toLocaleDateString('en-US', options);
}

// Format number with commas
function formatNumber(number) {
    return number.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// Back button functionality
function goBack() {
    window.history.back();
}

// Confirm delete
function confirmDelete(message = 'Are you sure you want to delete this item?') {
    return confirm(message);
}

// Handle form submission with AJAX
function submitFormAjax(formId, successCallback) {
    $(`#${formId}`).submit(function(e) {
        e.preventDefault();
        const form = $(this);
        const url = form.attr('action');
        
        $.ajax({
            type: 'POST',
            url: url,
            data: form.serialize(),
            success: function(response) {
                if (successCallback) {
                    successCallback(response);
                }
            },
            error: function(xhr, status, error) {
                alert('An error occurred. Please try again.');
            }
        });
    });
}

// Initialize DataTables
function initDataTable(tableId, options = {}) {
    const defaultOptions = {
        responsive: true,
        pageLength: 10,
        language: {
            search: 'Search:',
            lengthMenu: 'Show _MENU_ entries',
            info: 'Showing _START_ to _END_ of _TOTAL_ entries',
            paginate: {
                first: 'First',
                last: 'Last',
                next: 'Next',
                previous: 'Previous'
            }
        }
    };
    
    return $(`#${tableId}`).DataTable({...defaultOptions, ...options});
}

// Initialize Select2
function initSelect2(selectId, options = {}) {
    const defaultOptions = {
        theme: 'bootstrap-5',
        width: '100%'
    };
    
    return $(`#${selectId}`).select2({...defaultOptions, ...options});
}

// Handle infinite scroll
function handleInfiniteScroll(containerSelector, loadMoreFunction, options = {}) {
    const defaultOptions = {
        offset: 100,
        loading: false
    };
    
    const settings = {...defaultOptions, ...options};
    
    $(window).scroll(function() {
        if (settings.loading) return;
        
        if ($(window).scrollTop() + $(window).height() > 
            $(containerSelector).offset().top + $(containerSelector).height() - settings.offset) {
            settings.loading = true;
            loadMoreFunction().then(() => {
                settings.loading = false;
            });
        }
    });
}

// Handle file upload with progress
function handleFileUpload(inputId, url, progressBarId, successCallback) {
    $(`#${inputId}`).change(function() {
        const file = this.files[0];
        const formData = new FormData();
        formData.append('file', file);
        
        $.ajax({
            url: url,
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            xhr: function() {
                const xhr = new window.XMLHttpRequest();
                xhr.upload.addEventListener('progress', function(e) {
                    if (e.lengthComputable) {
                        const percent = Math.round((e.loaded / e.total) * 100);
                        $(`#${progressBarId}`).width(`${percent}%`).text(`${percent}%`);
                    }
                }, false);
                return xhr;
            },
            success: function(response) {
                if (successCallback) {
                    successCallback(response);
                }
            },
            error: function(xhr, status, error) {
                alert('File upload failed. Please try again.');
            }
        });
    });
}

// Handle chart responsiveness
function handleChartResize(chart) {
    let resizeTimer;
    $(window).resize(function() {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function() {
            chart.resize();
        }, 250);
    });
} 