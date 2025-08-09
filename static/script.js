const Toast = Swal.mixin({
    toast: true,
    position: 'top-end',
    showConfirmButton: false,
    timer: 2000,
    timerProgressBar: true,
    didOpen: (toast) => {
        toast.addEventListener('mouseenter', Swal.stopTimer);
        toast.addEventListener('mouseleave', Swal.resumeTimer);
    }
});

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
    return Toast.fire({
      icon,    // success / error / warning / info / question
      title,
      text     // 可不傳，用於補充說明
    });
}

// 主題切換功能
class ThemeManager {
    constructor() {
        this.themeToggle = null;
        this.themeIcon = null;
        this.currentTheme = this.getStoredTheme() || 'light';
        this.init();
    }

    init() {
        // 等待DOM載入完成後初始化
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.setup());
        } else {
            this.setup();
        }
    }

    setup() {
        this.themeToggle = document.getElementById('themeToggle');
        this.themeIcon = document.getElementById('themeIcon');
        
        if (this.themeToggle && this.themeIcon) {
            // 設置初始主題
            this.applyTheme(this.currentTheme);
            
            // 綁定點擊事件
            this.themeToggle.addEventListener('click', () => this.toggleTheme());
            
            // 監聽系統主題變化
            if (window.matchMedia) {
                window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
                    if (!this.hasStoredTheme()) {
                        this.currentTheme = e.matches ? 'dark' : 'light';
                        this.applyTheme(this.currentTheme);
                    }
                });
            }
        }
    }

    getStoredTheme() {
        try {
            return localStorage.getItem('theme');
        } catch (e) {
            return null;
        }
    }

    setStoredTheme(theme) {
        try {
            localStorage.setItem('theme', theme);
        } catch (e) {
            console.warn('無法保存主題設置到本地存儲');
        }
    }

    hasStoredTheme() {
        return this.getStoredTheme() !== null;
    }

    getSystemTheme() {
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            return 'dark';
        }
        return 'light';
    }

    toggleTheme() {
        this.currentTheme = this.currentTheme === 'light' ? 'dark' : 'light';
        this.applyTheme(this.currentTheme);
        this.setStoredTheme(this.currentTheme);
        
        // 顯示切換提示
        const themeName = this.currentTheme === 'dark' ? '夜晚模式' : '白天模式';
        showToast('主題已切換', `已切換至${themeName}`, 'success');
    }

    applyTheme(theme) {
        const htmlElement = document.documentElement;
        
        if (theme === 'dark') {
            htmlElement.setAttribute('data-theme', 'dark');
            if (this.themeIcon) {
                this.themeIcon.className = 'fas fa-sun';
                this.themeToggle.title = '切換至白天模式';
            }
        } else {
            htmlElement.removeAttribute('data-theme');
            if (this.themeIcon) {
                this.themeIcon.className = 'fas fa-moon';
                this.themeToggle.title = '切換至夜晚模式';
            }
        }
        
        this.currentTheme = theme;
    }

    getCurrentTheme() {
        return this.currentTheme;
    }
}

// 創建全局主題管理器實例
const themeManager = new ThemeManager();