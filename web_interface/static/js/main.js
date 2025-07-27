// Initialize Socket.IO connection
const socket = io();

// Initialize CodeMirror editor
let editor = null;

document.addEventListener('DOMContentLoaded', function() {
    // Initialize the CodeMirror editor
    const textarea = document.getElementById('claude-md-editor');
    editor = CodeMirror.fromTextArea(textarea, {
        mode: 'markdown',
        theme: 'monokai',
        lineNumbers: true,
        lineWrapping: true,
        autofocus: true
    });

    // Load initial CLAUDE.md content
    loadClaudeMd();

    // Load initial config and personas
    loadConfig();
    loadPersonas();

    // Set up event listeners
    document.getElementById('save-btn').addEventListener('click', saveClaudeMd);
    document.getElementById('reload-btn').addEventListener('click', loadClaudeMd);
    document.getElementById('preview-btn').addEventListener('click', previewMarkdown);

    // Setting change listeners
    document.getElementById('llm-select').addEventListener('change', updateConfig);
    document.getElementById('voice-select').addEventListener('change', updateConfig);
    document.getElementById('persona-select').addEventListener('change', updateConfig);
    document.getElementById('claude-code-toggle').addEventListener('change', updateConfig);
    
    // Persona management listeners
    document.getElementById('add-persona-btn').addEventListener('click', addPersona);

    // Refresh LAURA image every 10 seconds
    setInterval(refreshLauraImage, 10000);
});

// Socket.IO event handlers
socket.on('connect', function() {
    console.log('Connected to server');
    updateStatus('Connected', 'success');
});

socket.on('disconnect', function() {
    console.log('Disconnected from server');
    updateStatus('Disconnected', 'error');
});

socket.on('status_changed', function(data) {
    // Update status display when server sends updates
    if (data.status) {
        document.getElementById('system-status').textContent = data.status;
    }
    if (data.model) {
        document.getElementById('current-model').textContent = data.model;
    }
    if (data.voice) {
        document.getElementById('current-voice').textContent = data.voice;
    }
    if (data.persona) {
        document.getElementById('current-persona').textContent = data.persona;
    }
});

// Load CLAUDE.md content
async function loadClaudeMd() {
    try {
        const response = await fetch('/api/claude_md');
        const data = await response.json();
        if (data.content) {
            editor.setValue(data.content);
            showNotification('CLAUDE.md loaded successfully', 'success');
        }
    } catch (error) {
        console.error('Error loading CLAUDE.md:', error);
        showNotification('Failed to load CLAUDE.md', 'error');
    }
}

// Save CLAUDE.md content
async function saveClaudeMd() {
    try {
        const content = editor.getValue();
        const response = await fetch('/api/claude_md', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ content: content })
        });
        
        if (response.ok) {
            showNotification('CLAUDE.md saved successfully', 'success');
        } else {
            throw new Error('Save failed');
        }
    } catch (error) {
        console.error('Error saving CLAUDE.md:', error);
        showNotification('Failed to save CLAUDE.md', 'error');
    }
}

// Preview markdown (placeholder - could open in new window)
function previewMarkdown() {
    const content = editor.getValue();
    // TODO: Implement markdown preview
    showNotification('Preview feature coming soon', 'info');
}

// Load configuration
async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        const config = await response.json();
        
        // Update UI with config values
        if (config.llm_model) {
            document.getElementById('llm-select').value = config.llm_model;
        }
        if (config.voice) {
            document.getElementById('voice-select').value = config.voice;
        }
        if (config.persona) {
            document.getElementById('persona-select').value = config.persona;
        }
        if (config.claude_code_enabled !== undefined) {
            document.getElementById('claude-code-toggle').checked = config.claude_code_enabled;
        }
    } catch (error) {
        console.error('Error loading config:', error);
    }
}

// Update configuration
async function updateConfig() {
    const config = {
        llm_model: document.getElementById('llm-select').value,
        voice: document.getElementById('voice-select').value,
        persona: document.getElementById('persona-select').value,
        claude_code_enabled: document.getElementById('claude-code-toggle').checked
    };

    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(config)
        });
        
        if (response.ok) {
            showNotification('Configuration updated', 'success');
            // Emit config change to server
            socket.emit('config_changed', config);
        }
    } catch (error) {
        console.error('Error updating config:', error);
        showNotification('Failed to update configuration', 'error');
    }
}

// Refresh LAURA image
function refreshLauraImage() {
    const img = document.getElementById('laura-display');
    // Add timestamp to force refresh
    img.src = `/api/current_image?t=${Date.now()}`;
}

// Update status display
function updateStatus(message, type = 'info') {
    const statusElement = document.getElementById('system-status');
    statusElement.textContent = message;
    statusElement.className = `value status-${type}`;
}

// Load personas
async function loadPersonas() {
    try {
        const response = await fetch('/api/personas');
        const data = await response.json();
        
        if (data.personas) {
            displayPersonas(data.personas);
            updatePersonaDropdown(data.personas);
        }
    } catch (error) {
        console.error('Error loading personas:', error);
        showNotification('Failed to load personas', 'error');
    }
}

// Display personas in the management section
function displayPersonas(personas) {
    const container = document.getElementById('personas-list');
    container.innerHTML = '';
    
    Object.entries(personas).forEach(([name, config]) => {
        const card = document.createElement('div');
        card.className = `persona-card ${['laura', 'client_default'].includes(name) ? 'essential' : ''}`;
        
        const voiceId = config.elevenlabs?.voice_name_or_id || 'Unknown';
        const displayName = config.display_name || '';
        
        card.innerHTML = `
            <h4>${name}</h4>
            <div class="voice-id">ID: ${voiceId}</div>
            ${displayName ? `<div class="voice-name">${displayName}</div>` : ''}
            <button class="delete-btn" onclick="deletePersona('${name}')" title="Delete persona">×</button>
        `;
        
        container.appendChild(card);
    });
}

// Update persona dropdown
function updatePersonaDropdown(personas) {
    const select = document.getElementById('persona-select');
    select.innerHTML = '';
    
    Object.keys(personas).forEach(name => {
        const option = document.createElement('option');
        option.value = name;
        option.textContent = name.charAt(0).toUpperCase() + name.slice(1);
        select.appendChild(option);
    });
}

// Add new persona
async function addPersona() {
    const name = document.getElementById('new-persona-name').value.trim().toLowerCase();
    const voiceId = document.getElementById('new-voice-id').value.trim();
    const voiceName = document.getElementById('new-voice-name').value.trim();
    
    if (!name || !voiceId) {
        showNotification('Persona name and voice ID are required', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/personas', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                name: name,
                voice_id: voiceId,
                voice_name: voiceName
            })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showNotification(`Persona '${name}' added successfully`, 'success');
            // Clear form
            document.getElementById('new-persona-name').value = '';
            document.getElementById('new-voice-id').value = '';
            document.getElementById('new-voice-name').value = '';
            // Reload personas
            loadPersonas();
        } else {
            showNotification(result.error || 'Failed to add persona', 'error');
        }
    } catch (error) {
        console.error('Error adding persona:', error);
        showNotification('Failed to add persona', 'error');
    }
}

// Delete persona
async function deletePersona(name) {
    if (!confirm(`Are you sure you want to delete the '${name}' persona?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/personas/${name}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showNotification(`Persona '${name}' deleted successfully`, 'success');
            loadPersonas();
        } else {
            showNotification(result.error || 'Failed to delete persona', 'error');
        }
    } catch (error) {
        console.error('Error deleting persona:', error);
        showNotification('Failed to delete persona', 'error');
    }
}

// Show notification
function showNotification(message, type = 'info') {
    // TODO: Implement toast notifications
    console.log(`[${type.toUpperCase()}] ${message}`);
}

// Add custom dark theme for CodeMirror
const style = document.createElement('style');
style.textContent = `
.cm-s-monokai.CodeMirror { background: #0a0a0a; color: #e0e0e0; }
.cm-s-monokai div.CodeMirror-selected { background: #333; }
.cm-s-monokai .CodeMirror-line::selection, .cm-s-monokai .CodeMirror-line > span::selection, .cm-s-monokai .CodeMirror-line > span > span::selection { background: rgba(73, 72, 62, .99); }
.cm-s-monokai .CodeMirror-line::-moz-selection, .cm-s-monokai .CodeMirror-line > span::-moz-selection, .cm-s-monokai .CodeMirror-line > span > span::-moz-selection { background: rgba(73, 72, 62, .99); }
.cm-s-monokai .CodeMirror-gutters { background: #1a1a1a; border-right: 1px solid #333; }
.cm-s-monokai .CodeMirror-guttermarker { color: #FFFFFF; }
.cm-s-monokai .CodeMirror-guttermarker-subtle { color: #666; }
.cm-s-monokai .CodeMirror-linenumber { color: #666; }
.cm-s-monokai .CodeMirror-cursor { border-left: 1px solid #e0e0e0; }
`;
document.head.appendChild(style);