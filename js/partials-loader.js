/**
 * MicTest - Partials Loader
 * Loads navbar and footer partials into the page
 */

class PartialsLoader {
  constructor() {
    this.basePath = '/partials';
  }

  async loadPartial(elementId, partialName) {
    const element = document.getElementById(elementId);
    if (!element) return;

    try {
      const response = await fetch(`${this.basePath}/${partialName}.html`);
      if (response.ok) {
        const html = await response.text();
        element.innerHTML = html;

        if (partialName === 'navbar') {
          this.setActiveNavLink();
        }
      }
    } catch (error) {
      console.error(`Error loading ${partialName}:`, error);
    }
  }

  setActiveNavLink() {
    const currentPath = window.location.pathname;
    const currentPage = this.getPageFromPath(currentPath);

    // Remove all active classes first
    document.querySelectorAll('#navbar-container .nav-link').forEach(link => {
      link.classList.remove('active');
      link.removeAttribute('aria-current');
    });

    document.querySelectorAll('#navbar-container .dropdown-item').forEach(link => {
      link.classList.remove('active');
    });

    // Set active class on matching link
    const activeLink = document.querySelector(`#navbar-container [data-page="${currentPage}"]`);
    if (activeLink) {
      activeLink.classList.add('active');
      activeLink.setAttribute('aria-current', 'page');

      // If it's a dropdown item, also highlight the parent dropdown
      const parentDropdown = activeLink.closest('.dropdown');
      if (parentDropdown) {
        const dropdownToggle = parentDropdown.querySelector('.dropdown-toggle');
        if (dropdownToggle) {
          dropdownToggle.classList.add('active');
        }
      }
    }
  }

  getPageFromPath(path) {
    // Remove trailing slash and get the last segment
    path = path.replace(/\/$/, '');

    if (path === '' || path === '/index.html' || path === '/index') {
      return 'index';
    }

    // Remove leading slash and .html extension
    return path.replace(/^\//, '').replace(/\.html$/, '');
  }

  async init() {
    await this.loadPartial('navbar-container', 'navbar');
    await this.loadPartial('footer-container', 'footer');
  }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  const loader = new PartialsLoader();
  loader.init();
});
