import './App.css';
import React from "react";
import Consultation from "./Pages/Consultation/Consultation";

const App = () => {
    return (
        <div className="app-container">
            <header className="floating-navbar-wrapper">
                <nav className="navbar floating-navbar">
                    <div className="container-fluid px-3 d-flex align-items-center justify-content-between">
                        <div className="d-flex align-items-center">
                            <img src="/logo.svg" height="34" width="34" className="d-inline-block align-top me-2 brand-logo-img" alt="ClinicaNLP"/>
                            <span className="brand-text">Clinica<span className="brand-accent">NLP</span></span>
                            <span className="badge ms-3 d-none d-sm-inline-block" style={{ background: '#e0f2fe', color: '#0369a1', borderRadius: '1rem', fontSize: '0.75rem', fontWeight: 600 }}>
                                Doctor-Patient Consultation Analyzer
                            </span>
                        </div>

                        <div className="d-flex align-items-center gap-2">
                            <span className="badge" style={{ background: '#dcfce7', color: '#15803d', borderRadius: '1rem', fontSize: '0.75rem', fontWeight: 600, padding: '6px 12px' }}>
                                ● NLP Model Online
                            </span>
                        </div>
                    </div>
                </nav>
            </header>

            <main className="main-content-flow">
                <Consultation />
            </main>

            <footer className="footer py-3 border-top mt-5" style={{ background: '#ffffff' }}>
                <div className="container d-flex align-items-center justify-content-between flex-wrap gap-2">
                    <div className="d-flex align-items-center">
                        <img src="/logo.svg" height="20" width="20" className="d-inline-block align-top me-2" alt="ClinicaNLP"/>
                        <span className="text-muted small">© 2026 ClinicaNLP • Natural Language Processing Mini-Project</span>
                    </div>
                    <span className="text-muted small">Clinical Dialogue & Health Records NLP</span>
                </div>
            </footer>
        </div>
    );
};

export default App;
