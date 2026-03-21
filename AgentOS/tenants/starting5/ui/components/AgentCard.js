/**
 * AgentCard.js — Visual representation of a Starting5 Agent
 */
const AgentCard = ({ position, name, model, onUpdate }) => {
    const isEmpty = !name || name.toLowerCase().includes('empty');
    
    return `
        <div class="roster-slot ${isEmpty ? 'empty' : ''}" onclick="window.location.hash = '${position}'">
            <span class="pos-label">${position}</span>
            <div class="agent-name ${isEmpty ? 'empty-slot' : ''}">${name || 'Empty Slot'}</div>
            ${model ? `<div class="agent-model">${model}</div>` : ''}
            <button class="btn-hire" onclick="event.stopPropagation(); ${isEmpty ? 'hire' : 'update'}('${position}')">
                ${isEmpty ? 'Hire' : 'Update'}
            </button>
        </div>
    `;
};

// Export for use in RosterPicker
window.AgentCard = AgentCard;
