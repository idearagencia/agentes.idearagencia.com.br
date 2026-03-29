// Dr. Licitação - Wizard Script v3 (Design Novo)

let currentStep = 1;
const totalSteps = 7;
const storageKey = 'drLicitacaoFormData';

let formData = {
    objeto: '', tipoObjeto: '', secretaria: '', valorEstimado: '', prazo: '', unidades: '',
    problema: '', justificativa: '', interessePublico: '',
    alternativas: [], justificativaEscolha: '',
    metodoPesquisa: '', documentosPreco: '', comentariosCusto: '',
    riscos: [], beneficios: '', impactosAmbientais: '',
    requisitosTecnicos: '', requisitosQualificacao: '',
    parcelamento: '', justificativaParcelamento: '', contratacoesCorrelatas: '',
    providencias: '', responsavelElaboracao: '', responsavelAprovacao: '',
    itensCompra: []
};

// ==================== STORAGE ====================
function getStorage() {
    try {
        if (typeof Storage === "undefined") return null;
        localStorage.setItem('test', 'test');
        localStorage.removeItem('test');
        return localStorage;
    } catch (e) {
        return sessionStorage;
    }
}

function saveFormData() {
    try {
        const storage = getStorage();
        if (!storage) return false;
        storage.setItem(storageKey, JSON.stringify(formData));
        return true;
    } catch (e) {
        return false;
    }
}

function loadFormData() {
    try {
        const storage = getStorage();
        if (!storage) return false;
        const saved = storage.getItem(storageKey);
        if (saved) {
            Object.assign(formData, JSON.parse(saved));
            return true;
        }
        return false;
    } catch (e) {
        return false;
    }
}

// ==================== NAVIGATION ====================
function changeStep(direction) {
    if (direction === 1 && !validateStep(currentStep)) {
        alert('Por favor, preencha todos os campos obrigatórios (*) desta etapa antes de prosseguir.');
        return;
    }
    const newStep = currentStep + direction;
    if (newStep < 1 || newStep > totalSteps) return;
    currentStep = newStep;
    updateUI();
    saveFormData();
}

function jumpToStep(targetStep) {
    if (targetStep <= currentStep) {
        currentStep = targetStep;
        updateUI();
        saveFormData();
        return;
    }
    if (targetStep > currentStep) {
        if (!validateStep(currentStep)) {
            alert('Por favor, preencha todos os campos obrigatórios desta etapa antes de prosseguir.');
            return;
        }
        currentStep = targetStep;
        updateUI();
        saveFormData();
    }
}

// ==================== UI UPDATES ====================
function updateUI() {
    // Update step panels
    document.querySelectorAll('.step-panel').forEach((el, i) => {
        el.classList.toggle('active', i + 1 === currentStep);
    });

    // Update progress steps
    document.querySelectorAll('.progress-track .step').forEach((step, i) => {
        const stepNum = i + 1;
        step.classList.toggle('active', stepNum === currentStep);
        step.classList.toggle('completed', stepNum < currentStep);
    });

    // Update progress bar
    const fill = document.getElementById('progressFill');
    if (fill) {
        const percent = ((currentStep - 1) / (totalSteps - 1)) * 100;
        fill.style.width = percent + '%';
    }

    // Update step title
    const titles = ['', 'Identificação', 'Necessidade', 'Alternativas', 'Custos', 'Riscos', 'Requisitos', 'Finalizar'];
    const titleEl = document.getElementById('stepTitle');
    if (titleEl) titleEl.textContent = titles[currentStep] || '';

    // Buttons
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    if (prevBtn) prevBtn.disabled = currentStep === 1;
    if (nextBtn) {
        if (currentStep === totalSteps) {
            nextBtn.style.display = 'none';
        } else {
            nextBtn.style.display = 'inline-flex';
            nextBtn.textContent = currentStep === totalSteps - 1 ? 'Finalizar →' : 'Próximo →';
        }
    }

    syncStepFields(currentStep);
    initializeAllCounters();
}

function syncStepFields(step) {
    const stepEl = document.getElementById('step' + step);
    if (!stepEl) return;
    stepEl.querySelectorAll('input, select, textarea').forEach(field => {
        const id = field.id;
        if (!id) return;
        if (formData.hasOwnProperty(id)) {
            const val = formData[id];
            if (field.type === 'checkbox') field.checked = val;
            else field.value = val;
        }
    });
}

function initializeAllCounters() {
    document.querySelectorAll('.char-count').forEach(counter => {
        const targetId = counter.getAttribute('data-for');
        const field = document.getElementById(targetId);
        if (field) {
            const current = field.value.length;
            const max = field.getAttribute('maxlength');
            counter.textContent = `${current}/${max}`;
        }
    });
}

// ==================== VALIDATION ====================
function validateStep(step) {
    const stepEl = document.getElementById('step' + step);
    if (!stepEl) return true;

    const tipo = document.getElementById('tipoObjeto')?.value;
    if ((tipo === 'obra' || tipo === 'servico_engenharia') && step >= 4) {
        return true; // Etapas 4-7 bloqueadas para obras em desenvolvimento
    }

    const requiredFields = stepEl.querySelectorAll('[required]');
    let valid = true;
    requiredFields.forEach(field => {
        const value = field.type === 'checkbox' ? field.checked : field.value;
        if (!value || (typeof value === 'string' && value.trim() === '')) {
            field.style.borderColor = 'var(--danger)';
            valid = false;
        } else {
            field.style.borderColor = '';
        }
    });

    // Validação especial para step 1: se bem/servico, precisa ter itens
    if (step === 1 && (tipo === 'bem' || tipo === 'servico')) {
        const temItens = (formData.itensCompra?.length || 0) > 0;
        if (!temItens) {
            alert('Para Bens ou Serviços, adicione pelo menos 1 item na tabela.');
            valid = false;
        }
    }

    return valid;
}

// ==================== TIPO DE OBJETO HANDLING ====================
function handleTipoObjetoChange() {
    const tipo = document.getElementById('tipoObjeto').value;
    const notaEl = document.getElementById('tipoNota');
    const itensField = document.getElementById('itensField');
    const itensLabel = document.getElementById('itensLabel');
    const itensNota = document.getElementById('itensNota');
    const valorField = document.getElementById('valorEstimado');

    if (tipo === 'obra' || tipo === 'servico_engenharia') {
        if (notaEl) {
            notaEl.textContent = 'Funcionalidade em desenvolvimento - formulário bloqueado';
            notaEl.style.display = 'block';
            notaEl.style.color = 'var(--danger)';
        }
        if (itensField) itensField.style.display = 'none';
        if (valorField) {
            valorField.readOnly = false;
            valorField.style.opacity = '1';
            valorField.style.cursor = 'auto';
            valorField.style.background = '';
        }

        const formFields = document.querySelectorAll('#step1 input, #step1 select, #step1 textarea');
        formFields.forEach(field => {
            if (field.type !== 'button' && field.tagName !== 'BUTTON') {
                field.disabled = true;
                field.style.opacity = '0.5';
                field.style.cursor = 'not-allowed';
            }
        });

        showBlockedOverlay('Esta funcionalidade está em desenvolvimento e será liberada em breve.');
    } else {
        if (notaEl) notaEl.style.display = 'none';
        removeBlockedOverlay();

        const formFields = document.querySelectorAll('#step1 input, #step1 select, #step1 textarea');
        formFields.forEach(field => {
            if (field.type !== 'button' && field.tagName !== 'BUTTON' && field.type !== 'checkbox') {
                field.disabled = false;
                field.style.opacity = '1';
                field.style.cursor = 'auto';
            }
        });

        if (tipo === 'bem' || tipo === 'servico') {
            if (itensField) {
                itensField.style.display = 'block';
                if (itensLabel) itensLabel.textContent = tipo === 'bem' ? 'Itens do Material/Produto' : 'Itens do Serviço (por mês)';
                if (itensNota) itensNota.textContent = tipo === 'bem'
                    ? 'Adicione todos os itens/materiais. O valor total será calculado automaticamente.'
                    : 'Adicione as linhas de serviço. O valor total será calculado automaticamente.';
            }
            if (valorField) {
                valorField.setAttribute('readonly', 'true');
                valorField.style.opacity = '0.8';
                valorField.style.cursor = 'not-allowed';
                valorField.style.backgroundColor = 'var(--surface)';
            }
        } else {
            if (itensField) itensField.style.display = 'none';
            if (valorField) {
                valorField.removeAttribute('readonly');
                valorField.style.opacity = '1';
                valorField.style.cursor = 'auto';
                valorField.style.backgroundColor = '';
            }
        }
    }

    recalculateTotalFromItems();
    saveFormData();
}

function showBlockedOverlay(message) {
    let overlay = document.getElementById('blockedOverlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'blockedOverlay';
        overlay.style.cssText = `
            position: fixed; top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.7); z-index: 9999;
            display: flex; align-items: center; justify-content: center;
            cursor: not-allowed;
        `;
        const content = document.createElement('div');
        content.style.cssText = `
            background: var(--surface); border: 2px solid var(--warning);
            border-radius: 12px; padding: 40px; max-width: 500px;
            text-align: center; color: var(--text);
        `;
        content.innerHTML = `
            <div style="font-size: 48px; margin-bottom: 16px;">🚧</div>
            <h3 style="color: var(--warning); margin-bottom: 12px;">Em desenvolvimento</h3>
            <p style="margin-bottom: 20px;">${message}</p>
            <button onclick="document.getElementById('blockedOverlay').remove()" 
                    style="background: var(--primary); color: white; border: none; 
                           padding: 10px 24px; border-radius: 8px; cursor: pointer;
                           font-weight: 600;">
                Entendi
            </button>
        `;
        overlay.appendChild(content);
        document.body.appendChild(overlay);
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) overlay.remove();
        });
    }
}

function removeBlockedOverlay() {
    const overlay = document.getElementById('blockedOverlay');
    if (overlay) overlay.remove();
}

// ==================== ITEMS TABLE ====================
const UNIDADES = [
    'un', 'kg', 'g', 'l', 'm', 'm²', 'pc', 'cx', 'rolo', 'pacote', 'kit', 'conjunto', 'par', 'h', 'dia', 'ano', 'mês', 'outro'
];

function addItem() {
    const tipo = document.getElementById('tipoObjeto').value;
    if (!tipo) {
        alert('Selecione primeiro o tipo de objeto.');
        return;
    }
    if (tipo !== 'bem' && tipo !== 'servico') {
        alert('Itens só podem ser adicionados para Bens ou Serviços.');
        return;
    }

    const tbody = document.getElementById('itemsTableBody');
    const row = document.createElement('tr');
    let options = UNIDADES.map(u => `<option value="${u}">${u}</option>`).join('');

    row.innerHTML = `
        <td><input type="text" placeholder="Descrição do item" class="item-desc" required></td>
        <td><select class="item-unit" required>${options}</select></td>
        <td><input type="number" min="1" placeholder="Qtd" class="item-qty" required></td>
        <td><input type="text" placeholder="R$ 0,00" class="item-price" required></td>
        <td class="item-total" data-index="${row.rowIndex}">R$ 0,00</td>
        <td style="text-align: center;"><button type="button" class="btn btn-danger btn-sm" onclick="removeItem(this)">×</button></td>
    `;
    tbody.appendChild(row);

    row.querySelector('.item-price').addEventListener('input', recalculateTotalFromItems);
    row.querySelector('.item-qty').addEventListener('input', recalculateTotalFromItems);
}

function removeItem(btn) {
    const row = btn.closest('tr');
    if (row) row.remove();
    recalculateTotalFromItems();
    saveFormData();
}

function recalculateTotalFromItems() {
    let total = 0;
    const rows = document.querySelectorAll('#itemsTableBody tr');
    rows.forEach(row => {
        const qty = parseFloat(row.querySelector('.item-qty').value) || 0;
        const price = parseCurrency(row.querySelector('.item-price').value) || 0;
        total += qty * price;
    });
    formData.valorEstimado = total;
    formData.itensCompra = Array.from(rows).map(row => ({
        descricao: row.querySelector('.item-desc').value || '',
        unidade: row.querySelector('.item-unit').value || '',
        quantidade: parseFloat(row.querySelector('.item-qty').value) || 0,
        valorUnitario: parseCurrency(row.querySelector('.item-price').value) || 0
    }));

    const valorField = document.getElementById('valorEstimado');
    if (valorField) valorField.value = formatCurrency(total);
}

function loadItemsFromFormData() {
    const tbody = document.getElementById('itemsTableBody');
    if (!tbody) return;
    tbody.innerHTML = '';

    (formData.itensCompra || []).forEach(item => {
        const row = document.createElement('tr');
        const options = UNIDADES.map(u => `<option value="${u}" ${item.unidade === u ? 'selected' : ''}>${u}</option>`).join('');
        row.innerHTML = `
            <td><input type="text" value="${item.descricao || ''}" placeholder="Descrição do item" class="item-desc" required></td>
            <td><select class="item-unit" required>${options}</select></td>
            <td><input type="number" value="${item.quantidade || ''}" min="1" placeholder="Qtd" class="item-qty" required></td>
            <td><input type="text" value="${item.valorUnitario ? formatCurrency(item.valorUnitario) : ''}" placeholder="R$ 0,00" class="item-price" required></td>
            <td class="item-total" data-index="${row.rowIndex}">${formatCurrency(item.total || (item.quantidade * item.valorUnitario))}</td>
            <td style="text-align: center;"><button type="button" class="btn btn-danger btn-sm" onclick="removeItem(this)">×</button></td>
        `;
        tbody.appendChild(row);

        row.querySelector('.item-price').addEventListener('input', recalculateTotalFromItems);
        row.querySelector('.item-qty').addEventListener('input', recalculateTotalFromItems);
    });

    recalculateTotalFromItems();
}

// ==================== ALTERNATIVES ====================
function addAlternative() {
    const container = document.getElementById('alternativesList');
    if (!container) return;
    const wrapper = document.createElement('div');
    wrapper.className = 'alternative-item';
    wrapper.style.cssText = 'display: flex; gap: 12px; margin-bottom: 12px;';
    wrapper.innerHTML = `
        <input type="text" placeholder="Nome da alternativa (ex: Locação)" class="alt-name" style="flex:1; padding:10px; border-radius:8px; border:1px solid var(--border); background:var(--surface); color:var(--text);" required>
        <input type="text" placeholder="Descrição breve da alternativa" class="alt-desc" style="flex:2; padding:10px; border-radius:8px; border:1px solid var(--border); background:var(--surface); color:var(--text);" required>
        <button type="button" class="btn btn-danger" style="padding:0 12px;" onclick="this.parentElement.remove()">×</button>
    `;
    container.appendChild(wrapper);
    saveFormData();
}

function loadAlternatives() {
    const container = document.getElementById('alternativesList');
    if (!container) return;
    container.innerHTML = '';
    (formData.alternativas || []).forEach(alt => {
        const wrapper = document.createElement('div');
        wrapper.className = 'alternative-item';
        wrapper.style.cssText = 'display: flex; gap: 12px; margin-bottom: 12px;';
        wrapper.innerHTML = `
            <input type="text" value="${alt.nome || ''}" placeholder="Nome da alternativa" class="alt-name" style="flex:1; padding:10px; border-radius:8px; border:1px solid var(--border); background:var(--surface); color:var(--text);" required>
            <input type="text" value="${alt.descricao || ''}" placeholder="Descrição" class="alt-desc" style="flex:2; padding:10px; border-radius:8px; border:1px solid var(--border); background:var(--surface); color:var(--text);" required>
            <button type="button" class="btn btn-danger" style="padding:0 12px;" onclick="this.parentElement.remove()">×</button>
        `;
        container.appendChild(wrapper);
    });
}

function saveAlternatives() {
    const items = [];
    document.querySelectorAll('#alternativesList .alternative-item').forEach(el => {
        const nome = el.querySelector('.alt-name').value;
        const descricao = el.querySelector('.alt-desc').value;
        items.push({ nome, descricao });
    });
    formData.alternativas = items;
}

// ==================== RISKS ====================
function addRisk() {
    const container = document.getElementById('risksList');
    if (!container) return;
    const wrapper = document.createElement('div');
    wrapper.className = 'risk-row';
    wrapper.style.cssText = 'display: flex; gap: 12px; margin-bottom: 12px;';
    wrapper.innerHTML = `
        <input type="text" placeholder="Descrição do risco" class="risk-desc" style="flex:2; padding:10px; border-radius:8px; border:1px solid var(--border); background:var(--surface); color:var(--text);" required>
        <input type="text" placeholder="Probabilidade (Baixa/Média/Alta)" class="risk-prob" style="flex:1; padding:10px; border-radius:8px; border:1px solid var(--border); background:var(--surface); color:var(--text);" required>
        <input type="text" placeholder="Impacto (Baixo/Médio/Alto)" class="risk-impact" style="flex:1; padding:10px; border-radius:8px; border:1px solid var(--border); background:var(--surface); color:var(--text);" required>
        <input type="text" placeholder="Mitigação proposta" class="risk-mit" style="flex:2; padding:10px; border-radius:8px; border:1px solid var(--border); background:var(--surface); color:var(--text);" required>
        <button type="button" class="btn btn-danger" style="padding:0 12px;" onclick="this.parentElement.remove()">×</button>
    `;
    container.appendChild(wrapper);
    saveFormData();
}

function loadRisks() {
    const container = document.getElementById('risksList');
    if (!container) return;
    container.innerHTML = '';
    (formData.riscos || []).forEach(risk => {
        const wrapper = document.createElement('div');
        wrapper.className = 'risk-row';
        wrapper.style.cssText = 'display: flex; gap: 12px; margin-bottom: 12px;';
        wrapper.innerHTML = `
            <input type="text" value="${risk.descricao || ''}" placeholder="Descrição do risco" class="risk-desc" style="flex:2; padding:10px; border-radius:8px; border:1px solid var(--border); background:var(--surface); color:var(--text);" required>
            <input type="text" value="${risk.probabilidade || ''}" placeholder="Probabilidade" class="risk-prob" style="flex:1; padding:10px; border-radius:8px; border:1px solid var(--border); background:var(--surface); color:var(--text);" required>
            <input type="text" value="${risk.impacto || ''}" placeholder="Impacto" class="risk-impact" style="flex:1; padding:10px; border-radius:8px; border:1px solid var(--border); background:var(--surface); color:var(--text);" required>
            <input type="text" value="${risk.mitigacao || ''}" placeholder="Mitigação" class="risk-mit" style="flex:2; padding:10px; border-radius:8px; border:1px solid var(--border); background:var(--surface); color:var(--text);" required>
            <button type="button" class="btn btn-danger" style="padding:0 12px;" onclick="this.parentElement.remove()">×</button>
        `;
        container.appendChild(wrapper);
    });
}

function saveRisks() {
    const items = [];
    document.querySelectorAll('#risksList .risk-row').forEach(el => {
        items.push({
            descricao: el.querySelector('.risk-desc').value,
            probabilidade: el.querySelector('.risk-prob').value,
            impacto: el.querySelector('.risk-impact').value,
            mitigacao: el.querySelector('.risk-mit').value
        });
    });
    formData.riscos = items;
}

// ==================== UTILITIES ====================
function formatCurrency(value) {
    if (value === '' || value === null || value === undefined) return '';
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value);
}

function parseCurrency(str) {
    if (!str) return 0;
    const cleaned = str.replace(/[^\d,.-]/g, '').replace(',', '.');
    const num = parseFloat(cleaned);
    return isNaN(num) ? 0 : num;
}

// ==================== EVENT LISTENERS ====================
function attachEventListeners() {
    document.querySelectorAll('#form input, #form select, #form textarea').forEach(field => {
        field.addEventListener('input', () => {
            const id = field.id;
            if (!id) return;
            const val = field.type === 'checkbox' ? field.checked : field.value;
            if (formData.hasOwnProperty(id)) formData[id] = val;
        });
        field.addEventListener('change', () => {
            const id = field.id;
            if (!id) return;
            const val = field.type === 'checkbox' ? field.checked : field.value;
            if (formData.hasOwnProperty(id)) formData[id] = val;
            saveFormData();
        });
    });
}

// ==================== INITIALIZATION ====================
document.addEventListener('DOMContentLoaded', () => {
    loadFormData();
    handleTipoObjetoChange();
    loadItemsFromFormData();
    loadAlternatives();
    loadRisks();
    updateUI();
    attachEventListeners();

    // Ensure at least one alternative and one risk
    if (formData.alternativas.length === 0) addAlternative();
    if (formData.riscos.length === 0) addRisk();

    saveFormData();
});
