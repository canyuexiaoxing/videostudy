(() => {
 'use strict';
 const root = document.documentElement, reduced = matchMedia('(prefers-reduced-motion: reduce)');
 root.classList.add('js');
 const header = document.querySelector('.site-header'), progress = document.querySelector('.reading-progress');
 let queued = false;
 function updateScroll() { const height = root.scrollHeight - innerHeight; progress.style.transform = `scaleX(${height > 0 ? Math.min(1, scrollY / height) : 0})`; header.classList.toggle('scrolled', scrollY > 24); queued = false; }
 addEventListener('scroll', () => { if (!queued) { queued = true; requestAnimationFrame(updateScroll); } }, { passive: true });
 addEventListener('resize', updateScroll, { passive: true }); updateScroll();
 if ('IntersectionObserver' in window) { const observer = new IntersectionObserver(entries => entries.forEach(entry => { if (entry.isIntersecting) { entry.target.classList.add('visible'); observer.unobserve(entry.target); } }), { threshold: .08, rootMargin: '0px 0px -20px 0px' }); document.querySelectorAll('.reveal').forEach(el => observer.observe(el)); }
 else document.querySelectorAll('.reveal').forEach(el => el.classList.add('visible'));
 const menuButton = document.querySelector('.menu-toggle'), nav = document.querySelector('.nav-links');
 function closeMenu() { menuButton.setAttribute('aria-expanded', 'false'); menuButton.setAttribute('aria-label', '打开导航'); nav.classList.remove('open'); }
 menuButton.addEventListener('click', () => { const open = menuButton.getAttribute('aria-expanded') !== 'true'; menuButton.setAttribute('aria-expanded', String(open)); menuButton.setAttribute('aria-label', open ? '关闭导航' : '打开导航'); nav.classList.toggle('open', open); });
 nav.querySelectorAll('a').forEach(a => a.addEventListener('click', closeMenu));
 document.addEventListener('keydown', e => { if (e.key === 'Escape') closeMenu(); }); document.addEventListener('click', e => { if (!header.contains(e.target)) closeMenu(); });
 const tabs = [...document.querySelectorAll('[role=tab]')];
 function activateTab(tab) { tabs.forEach(item => { const active = item === tab; item.setAttribute('aria-selected', String(active)); item.tabIndex = active ? 0 : -1; document.getElementById(item.getAttribute('aria-controls')).hidden = !active; }); }
 tabs.forEach((tab, index) => { tab.addEventListener('click', () => activateTab(tab)); tab.addEventListener('keydown', e => { let next; if (e.key === 'ArrowRight') next = (index + 1) % tabs.length; if (e.key === 'ArrowLeft') next = (index + tabs.length - 1) % tabs.length; if (e.key === 'Home') next = 0; if (e.key === 'End') next = tabs.length - 1; if (next !== undefined) { e.preventDefault(); activateTab(tabs[next]); tabs[next].focus(); } }); });
 const clock = document.getElementById('demo-time'), play = document.getElementById('demo-play');
 let seconds = 12 * 60 + 43, playback = null;
 function renderClock() { clock.textContent = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`; const value = `${Math.min(100, seconds / (21 * 60 + 53) * 100)}%`; document.querySelector('.demo-track span').style.width = value; document.querySelector('.demo-track i').style.left = value; }
 function stopPlayback() { clearInterval(playback); playback = null; play.setAttribute('aria-pressed', 'false'); play.setAttribute('aria-label', '播放演示'); play.querySelector('use').setAttribute('href', '#i-play'); document.body.classList.remove('demo-playing'); }
 play.addEventListener('click', () => { if (playback) return stopPlayback(); play.setAttribute('aria-pressed', 'true'); play.setAttribute('aria-label', '暂停演示'); play.querySelector('use').setAttribute('href', '#i-pause'); document.body.classList.add('demo-playing'); playback = setInterval(() => { seconds = (seconds + 1) % (21 * 60 + 54); renderClock(); }, 1000); });
 document.addEventListener('visibilitychange', () => { if (document.hidden) stopPlayback(); });
 function seek(time, caption) { stopPlayback(); const [min, sec] = time.split(':').map(Number); seconds = min * 60 + sec; renderClock(); if (caption) document.getElementById('lesson-caption').textContent = caption; document.getElementById('evidence-label').textContent = `已定位讲解 · ${time}`; if (!reduced.matches) document.querySelector('.lesson-board').animate([{ filter: 'brightness(1.18)' }, { filter: 'brightness(1)' }], { duration: 650, easing: 'ease-out' }); }
 document.querySelectorAll('.map-node').forEach(node => node.addEventListener('click', () => { document.querySelectorAll('.map-node').forEach(other => other.classList.toggle('active', node === other)); seek(node.dataset.time, node.dataset.caption); }));
 document.querySelectorAll('[data-seek]').forEach(button => button.addEventListener('click', () => seek(button.dataset.seek, '“当两点无限靠近时，割线就趋近于切线。”'))); renderClock();
 const faqItems = [...document.querySelectorAll('.faq-list details')]; faqItems.forEach(item => item.addEventListener('toggle', () => { if (item.open) faqItems.forEach(other => { if (other !== item) other.open = false; }); }));
 const toast = document.querySelector('.toast'); let toastTimeout;
 function dismissToast() { toast.classList.remove('visible'); clearTimeout(toastTimeout); }
 toast.querySelector('button').addEventListener('click', dismissToast);
 document.querySelectorAll('.download-link').forEach(link => link.addEventListener('click', () => { clearTimeout(toastTimeout); toast.classList.add('visible'); toastTimeout = setTimeout(dismissToast, 7000); }));
 const platform = navigator.userAgentData?.platform || navigator.platform || ''; if (platform && !/win/i.test(platform)) document.getElementById('platform-note').hidden = false;
})();
