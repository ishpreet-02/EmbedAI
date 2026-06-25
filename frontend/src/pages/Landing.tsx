import { Link } from 'react-router-dom'
import { Bot, Zap, Globe, MessageSquare, Code, Shield, BarChart3, Clock, ChevronDown } from 'lucide-react'
import { useState } from 'react'

function FAQItem({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false)
  return (
    <div className={`faq-item${open ? ' open' : ''}`} onClick={() => setOpen(!open)}>
      <div className="faq-q">
        <span>{q}</span>
        <ChevronDown size={16} className="faq-chevron" />
      </div>
      {open && <p className="faq-a">{a}</p>}
    </div>
  )
}

export default function Landing() {
  return (
    <div className="landing">
      {/* Nav */}
      <header className="landing-nav">
        <Link to="/" className="landing-logo">
          <Bot size={22} />
          EmbedAI
        </Link>
        <div className="landing-nav-actions">
          <Link to="/login" className="btn-secondary">Log in</Link>
          <Link to="/signup" className="btn-primary">Get started free</Link>
        </div>
      </header>

      {/* Hero */}
      <section className="landing-hero">
        <div className="hero-badge">
          <Zap size={13} />
          No code required
        </div>
        <h1 className="hero-title">
          Turn your website<br />
          into a <span>support agent</span>
        </h1>
        <p className="hero-subtitle">
          Paste your URL. Get an AI chatbot trained on your entire site — in minutes.
        </p>
        <div className="hero-actions">
          <Link to="/signup" className="btn-primary btn-lg">
            Start building free →
          </Link>
          <Link to="/login" className="btn-secondary">
            Log in
          </Link>
        </div>
      </section>

      {/* Product mockup */}
      <section className="landing-mockup">
        <div className="mockup-browser">
          <div className="mockup-dots">
            <span /><span /><span />
          </div>
          <div className="mockup-content">
            <div className="mockup-left">
              <div className="mockup-url-bar">
                <Globe size={13} />
                <span>yogastudio.com</span>
              </div>
              <div className="mockup-text-lines">
                <div className="mockup-line w80" />
                <div className="mockup-line w60" />
                <div className="mockup-line w90" />
                <div className="mockup-line w45" />
                <div className="mockup-line w70" />
              </div>
            </div>
            <div className="mockup-widget">
              <div className="mockup-widget-header">
                <div className="mockup-widget-dot" />
                AI Assistant
              </div>
              <div className="mockup-widget-body">
                <div className="mockup-msg visitor">Do you have beginner classes?</div>
                <div className="mockup-msg bot">Yes! We offer beginner yoga every Saturday at 9 AM and Wednesday at 6 PM. No experience needed — just bring a mat.</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="landing-steps">
        <h2 className="steps-heading">How it works</h2>
        <div className="steps-grid">
          <div className="step-card">
            <div className="step-icon">
              <Globe size={20} />
            </div>
            <h3 className="step-title">Paste your URL</h3>
            <p className="step-desc">
              Our crawler visits every page on your site, extracts the content,
              and builds a knowledge base automatically.
            </p>
          </div>
          <div className="step-card">
            <div className="step-icon">
              <Code size={20} />
            </div>
            <h3 className="step-title">Copy one line of code</h3>
            <p className="step-desc">
              Add a single <code>&lt;script&gt;</code> tag to your site. The chat
              bubble appears instantly — no configuration needed.
            </p>
          </div>
          <div className="step-card">
            <div className="step-icon">
              <MessageSquare size={20} />
            </div>
            <h3 className="step-title">Visitors get answers</h3>
            <p className="step-desc">
              Your chatbot responds using only your website content.
              No hallucinations, no off-topic answers.
            </p>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="landing-features">
        <h2 className="features-heading">Everything you need, nothing you don't</h2>
        <div className="features-grid">
          <div className="feature-card">
            <Shield size={18} className="feature-icon" />
            <h3>Grounded answers only</h3>
            <p>The AI answers strictly from your site's content. If it doesn't know, it says so.</p>
          </div>
          <div className="feature-card">
            <Clock size={18} className="feature-icon" />
            <h3>Ready in 5 minutes</h3>
            <p>Scraping, embedding, and deployment happen automatically. No training data to prepare.</p>
          </div>
          <div className="feature-card">
            <BarChart3 size={18} className="feature-icon" />
            <h3>See every conversation</h3>
            <p>Your dashboard logs every visitor question. Learn what your customers actually ask.</p>
          </div>
          <div className="feature-card">
            <Zap size={18} className="feature-icon" />
            <h3>Streaming responses</h3>
            <p>Answers appear word by word in real time, just like ChatGPT. No waiting for full responses.</p>
          </div>
          <div className="feature-card">
            <Globe size={18} className="feature-icon" />
            <h3>Works on any site</h3>
            <p>Static HTML, React, Next.js, WordPress — the crawler handles JavaScript-rendered pages too.</p>
          </div>
          <div className="feature-card">
            <Code size={18} className="feature-icon" />
            <h3>One-line embed</h3>
            <p>A single script tag. No npm install, no build step, no iframes. It just works.</p>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="landing-faq">
        <h2 className="faq-heading">Frequently asked questions</h2>
        <div className="faq-list">
          <FAQItem
            q="How does the chatbot learn from my website?"
            a="When you paste your URL, our system launches a headless browser that visits every page on your site. It extracts the readable content, splits it into chunks, and converts each chunk into a vector embedding stored in a database. When a visitor asks a question, we find the most relevant chunks and pass them to an LLM to generate an accurate answer."
          />
          <FAQItem
            q="Will it make up information that's not on my site?"
            a="No. The AI is explicitly instructed to answer only using your website content. If the answer isn't in the data, it responds with 'I don't have that information' and suggests contacting you directly."
          />
          <FAQItem
            q="How long does setup take?"
            a="Most websites are fully indexed in 2–3 minutes. You'll see the status update in real time on your dashboard. Once it says 'Ready', you can copy the embed code and start chatting."
          />
          <FAQItem
            q="Does it work on React / Next.js / single-page apps?"
            a="Yes. We use Playwright (a headless Chromium browser) for scraping, which executes JavaScript and waits for content to render — just like a real browser. This handles SPAs that traditional scrapers can't."
          />
          <FAQItem
            q="What does it cost?"
            a="The platform is free to use during beta. Scraping, embedding, and AI responses are all included at no cost."
          />
        </div>
      </section>

      {/* Final CTA */}
      <section className="landing-cta">
        <h2 className="cta-heading">Ready to try it?</h2>
        <p className="cta-desc">Create your first chatbot in under 5 minutes. No credit card required.</p>
        <Link to="/signup" className="btn-primary btn-lg">
          Get started free →
        </Link>
      </section>

      {/* Footer */}
      <footer className="landing-footer">
        <div className="footer-inner">
          <div className="footer-brand">
            <Bot size={15} />
            EmbedAI
          </div>
          <div className="footer-tech">
            Built with React, FastAPI, LangChain, and LLaMA 3
          </div>
        </div>
      </footer>
    </div>
  )
}
