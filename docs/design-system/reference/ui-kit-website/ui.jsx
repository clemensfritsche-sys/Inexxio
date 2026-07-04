// INEXXIO UI kit — shared atoms (Swiss-editorial)
const { useState, useEffect, useRef } = React;

function Icon({ name, size = 18, color, cls }) {
  useEffect(() => { if (window.lucide) window.lucide.createIcons(); });
  return <i className={cls} data-lucide={name} style={{ width: size, height: size, color, display: 'inline-flex' }}></i>;
}

function Button({ variant = 'primary', size, children, icon, iconRight, onClick }) {
  const cls = `btn btn-${variant}${size === 'lg' ? ' btn-lg' : ''}`;
  return (
    <button className={cls} onClick={onClick}>
      {icon && <Icon name={icon} size={17} />}
      {children}
      {iconRight && <Icon name={iconRight} size={17} />}
    </button>
  );
}

function Eyebrow({ children }) { return <span className="eyebrow">{children}</span>; }

function Check({ children }) {
  return <li><span className="ck"><Icon name="check" size={16} /></span><span>{children}</span></li>;
}

// Swiss section header: index + eyebrow in the meta column, headline + sub in main
function SectionHead({ index, eyebrow, title, sub, center }) {
  return (
    <div className={`section-head${center ? ' center' : ''}`}>
      <div className="sh-meta">
        {index && <span className="idx">{index}</span>}
        {eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}
      </div>
      <div className="sh-main">
        <h2 className="h-sec">{title}</h2>
        {sub && <p>{sub}</p>}
      </div>
    </div>
  );
}

// scroll-reveal wrapper
function Reveal({ children, tag = 'div', className = '' }) {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current; if (!el) return;
    const io = new IntersectionObserver((es) => {
      es.forEach(e => { if (e.isIntersecting) { el.classList.add('in'); io.unobserve(el); } });
    }, { threshold: 0.12 });
    io.observe(el); return () => io.disconnect();
  }, []);
  const Tag = tag;
  return <Tag ref={ref} className={`reveal ${className}`}>{children}</Tag>;
}

const ASSET = '../../assets/';
Object.assign(window, { Icon, Button, Eyebrow, Check, SectionHead, Reveal, ASSET, React, useState, useEffect, useRef });
