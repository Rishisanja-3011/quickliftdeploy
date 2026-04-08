document.addEventListener('DOMContentLoaded', () => {
    
    // Helper to show alerts
    const showAlert = (message, type = 'error') => {
        const alertBox = document.getElementById('alertMessage');
        if (alertBox) {
            alertBox.textContent = message;
            alertBox.className = `alert alert-${type}`;
            alertBox.style.display = 'block';
            
            // Auto hide after 3 seconds
            setTimeout(() => {
                alertBox.style.display = 'none';
            }, 3000);
        }
    };

    // --- Login Logic ---
    // const loginForm = document.getElementById('loginForm');
    // if (loginForm) {
    //     loginForm.addEventListener('submit', (e) => {
    //        // e.preventDefault();
    //         const username = document.getElementById('username').value;
    //         const password = document.getElementById('password').value;
    //         const btn = loginForm.querySelector('button');

    //         // Basic validation
    //         if (!username || !password) {
    //             showAlert('Please fill in all fields');
    //             return;
    //         }

    //         // Simulate API call
    //         btn.textContent = 'Logging in...';
    //         btn.disabled = true;

    //         setTimeout(() => {
    //             // Mock login success
    //             const user = {
    //                 username: username,
    //                 email: 'mock@example.com', // Placeholder since we logged in with username
    //                 name: username, 
    //                 token: 'mock-jwt-token-123'
    //             };
                
    //             localStorage.setItem('tripShareUser', JSON.stringify(user));
    //             window.location.href = '/dashboard';
    //         }, 1500);
    //     });
    // }

    // --- Register Logic ---
    
    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        // File input name display
        const authIdInput = document.getElementById('authId');
        const fileNameDisplay = document.getElementById('fileName');
        
        if (authIdInput && fileNameDisplay) {
            authIdInput.addEventListener('change', function() {
                if (this.files && this.files[0]) {
                    fileNameDisplay.textContent = `Selected: ${this.files[0].name}`;
                } else {
                    fileNameDisplay.textContent = '';
                }
            });
        }

        registerForm.addEventListener('submit', (e) => {
           // e.preventDefault();
            const fullname = document.getElementById('fullname').value;
            const username = document.getElementById('username').value;
            const email = document.getElementById('email').value;
            const contact = document.getElementById('contact').value;
            const city = document.getElementById('city').value;
            const gender = document.getElementById('gender').value;
            const password = document.getElementById('password').value;
            const confirmPassword = document.getElementById('confirm-password').value;
            const authId = document.getElementById('authId').files[0];
            const btn = registerForm.querySelector('button');

            if (password !== confirmPassword) {
                showAlert('Passwords do not match');
                return;
            }

            if (!authId) {
                showAlert('Please upload a Government ID for verification');
                return;
            }

            // Simulate API call
            btn.textContent = 'Creating Account...';
            btn.disabled = true;

            setTimeout(() => {
                // Store temp user data for OTP verification
                const tempUser = {
                    fullname,
                    username,
                    email,
                    contact,
                    city,
                    gender
                    // In real app, never store plain text password
                };
                sessionStorage.setItem('tempRegisterUser', JSON.stringify(tempUser));
                
                // Simulate sending OTP
                // console.log('OTP Sent: 1234'); 
                
                // window.location.href = '/otp';
            }, 2000);
        });
    }

    // --- Fallback Login Navigation ---
    const ensureLoginRedirect = () => {
        const links = document.querySelectorAll('a');
        links.forEach(a => {
            const text = (a.textContent || '').trim().toLowerCase();
            const hrefAttr = a.getAttribute('href');
            if (text === 'login' && (!hrefAttr || hrefAttr === '#')) {
                a.addEventListener('click', (e) => {
                    e.preventDefault();
                    window.location.href = '/login';
                });
            }
        });
    };
    ensureLoginRedirect();

    // --- OTP Logic ---
    const otpForm = document.getElementById('otpForm');
    if (otpForm) {
        const inputs = document.querySelectorAll('.otp-input');
        
        // Auto-focus next input
        inputs.forEach((input, index) => {
            input.addEventListener('keyup', (e) => {
                if (e.key >= 0 && e.key <= 9) {
                    if (index < inputs.length - 1) {
                        inputs[index + 1].focus();
                    }
                } else if (e.key === 'Backspace') {
                    if (index > 0) {
                        inputs[index - 1].focus();
                    }
                }
            });
        });

        otpForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const btn = otpForm.querySelector('button');
            
            let otp = '';
            inputs.forEach(input => otp += input.value);

            if (otp.length !== 4) {
                showAlert('Please enter the full 4-digit code');
                return;
            }

            btn.textContent = 'Verifying...';
            btn.disabled = true;

            setTimeout(() => {
                const tempUser = JSON.parse(sessionStorage.getItem('tempRegisterUser'));
                
                if (tempUser) {
                    // Create actual user session
                    const user = {
                        email: tempUser.email,
                        username: tempUser.username,
                        name: tempUser.fullname,
                        contact: tempUser.contact,
                        city: tempUser.city,
                        gender: tempUser.gender,
                        token: 'mock-jwt-token-new-user'
                    };
                    localStorage.setItem('tripShareUser', JSON.stringify(user));
                    sessionStorage.removeItem('tempRegisterUser'); 
                    
                    window.location.href = '/dashboard';
                } else {
                    // Fallback
                     const user = {
                        email: 'verified@example.com',
                        username: 'VerifiedUser',
                        name: 'Verified User',
                        token: 'mock-jwt-token-verified'
                    };
                    localStorage.setItem('tripShareUser', JSON.stringify(user));
                    window.location.href = '/dashboard';
                }
            }, 1500);
        });

        // Resend OTP
        const resendLink = document.getElementById('resendOtp');
        if (resendLink) {
            resendLink.addEventListener('click', (e) => {
                e.preventDefault();
                showAlert('New code sent to your email', 'success');
            });
        }
    }

    // --- Forgot Password Logic ---
    const forgotPasswordForm = document.getElementById('forgotPasswordForm');
    if (forgotPasswordForm) {
        forgotPasswordForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const email = document.getElementById('email').value;
            const btn = forgotPasswordForm.querySelector('button');

            if (!email) {
                showAlert('Please enter your email');
                return;
            }

            btn.textContent = 'Sending...';
            btn.disabled = true;

            setTimeout(() => {
                sessionStorage.setItem('resetEmail', email);
                window.location.href = '/otp'; 
            }, 1500);
        });
    }

    // --- Dashboard / Logout Logic ---
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', () => {
            localStorage.removeItem('tripShareUser');
            window.location.href = '/logout';
        });
    }

});
