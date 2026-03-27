/**
 * RosterPicker.js — Main logic for the Starting5 Roster selection
 */
class RosterPicker {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.roster = {
            "Point Guard": { name: "Alpha-1", model: "Gemini 2.5 Pro" },
            "Shooting Guard": { name: null, model: null },
            "Small Forward": { name: null, model: null },
            "Power Forward": { name: null, model: null },
            "Center": { name: "Omega-Vault", model: "Gemini 1.5 Flash" }
        };
        this.render();
    }

    render() {
        if (!this.container) return;
        
        let html = '';
        const positions = ["Point Guard", "Shooting Guard", "Small Forward", "Power Forward", "Center"];
        
        positions.forEach(pos => {
            const agent = this.roster[pos];
            html += window.AgentCard({
                position: pos,
                name: agent.name,
                model: agent.model
            });
        });
        
        this.container.innerHTML = html;
    }

    updateAgent(position, name, model) {
        this.roster[position] = { name, model };
        this.render();
    }
}

// Initialize on load
window.addEventListener('DOMContentLoaded', () => {
    window.rosterPicker = new RosterPicker('roster-container');
});
