var dagfuncs = window.dashAgGridFunctions = window.dashAgGridFunctions || {};

(function () {
    var BLANK_FILTER_TOKEN = "__laundry_blank__";

    function getFilterConfig(params) {
        var colDef = params && params.column && params.column.getColDef ? params.column.getColDef() : params.colDef || {};
        return (params && params.filterParams) || colDef.filterParams || {};
    }

    function normalizeOption(rawOption) {
        if (rawOption && typeof rawOption === "object") {
            var value = rawOption.value == null || rawOption.value === "" ? BLANK_FILTER_TOKEN : String(rawOption.value);
            var label = rawOption.label == null ? (value === BLANK_FILTER_TOKEN ? "(Blank)" : value) : String(rawOption.label);
            return { value: value, label: label };
        }

        if (rawOption == null || rawOption === "") {
            return { value: BLANK_FILTER_TOKEN, label: "(Blank)" };
        }

        return { value: String(rawOption), label: String(rawOption) };
    }

    function getOptions(params) {
        var rawValues = getFilterConfig(params).values || [];
        return rawValues.map(normalizeOption);
    }

    function buildOptionMap(options) {
        var optionMap = new Map();
        options.forEach(function (option) {
            optionMap.set(option.value, option.label);
        });
        return optionMap;
    }

    function encodeValue(value) {
        if (value == null || value === "") {
            return BLANK_FILTER_TOKEN;
        }
        return String(value);
    }

    function allOptionValues(options) {
        return options.map(function (option) {
            return option.value;
        });
    }

    function selectedSetFromModel(model, options) {
        if (model && Array.isArray(model.values)) {
            return new Set(
                model.values.map(function (value) {
                    return String(value);
                })
            );
        }

        return new Set(allOptionValues(options));
    }

    function summaryFromModel(model, optionMap) {
        if (!model || !Array.isArray(model.values)) {
            return "All";
        }

        if (model.values.length === 0) {
            return "None";
        }

        var labels = model.values.map(function (value) {
            return optionMap.get(String(value)) || String(value);
        });

        if (labels.length === 1) {
            return labels[0];
        }

        if (labels.length <= 3) {
            return labels.join(", ");
        }

        return labels[0] + " +" + (labels.length - 1);
    }

    function stopEvent(event) {
        if (!event) {
            return;
        }

        event.preventDefault();
        event.stopPropagation();
    }

    dagfuncs.LaundrySetFilter = class {
        init(params) {
            this.params = params;
            this.options = getOptions(params);
            this.optionMap = buildOptionMap(this.options);
            this.selectedValues = new Set(allOptionValues(this.options));
            this.searchText = "";

            this.eGui = document.createElement("div");
            this.eGui.className = "laundry-set-filter-menu";

            this.eSearchInput = document.createElement("input");
            this.eSearchInput.className = "laundry-set-filter-search";
            this.eSearchInput.type = "search";
            this.eSearchInput.placeholder = "Search values";
            this.eSearchInput.addEventListener("input", this.onSearchInput.bind(this));

            this.eActionRow = document.createElement("div");
            this.eActionRow.className = "laundry-set-filter-actions";

            this.eResetButton = this.createActionButton("Reset", this.onResetClick.bind(this));
            this.eNoneButton = this.createActionButton("None", this.onNoneClick.bind(this));
            this.eActionRow.appendChild(this.eResetButton);
            this.eActionRow.appendChild(this.eNoneButton);

            this.eList = document.createElement("div");
            this.eList.className = "laundry-set-filter-list";

            this.eGui.appendChild(this.eSearchInput);
            this.eGui.appendChild(this.eActionRow);
            this.eGui.appendChild(this.eList);

            this.setModel(null);
        }

        getGui() {
            return this.eGui;
        }

        createActionButton(label, onClick) {
            var button = document.createElement("button");
            button.className = "laundry-set-filter-action";
            button.type = "button";
            button.textContent = label;
            button.addEventListener("click", onClick);
            return button;
        }

        onSearchInput(event) {
            this.searchText = String(event.target.value || "").trim().toLowerCase();
            this.renderOptions();
        }

        onResetClick(event) {
            stopEvent(event);
            this.selectedValues = new Set(allOptionValues(this.options));
            this.renderOptions();
            this.notifyFilterChanged();
        }

        onNoneClick(event) {
            stopEvent(event);
            this.selectedValues = new Set();
            this.renderOptions();
            this.notifyFilterChanged();
        }

        matchesSearch(option) {
            if (!this.searchText) {
                return true;
            }

            return option.label.toLowerCase().indexOf(this.searchText) >= 0;
        }

        renderOptions() {
            this.eList.replaceChildren();

            var visibleOptions = this.options.filter(this.matchesSearch.bind(this));
            if (!visibleOptions.length) {
                var emptyState = document.createElement("div");
                emptyState.className = "laundry-set-filter-empty";
                emptyState.textContent = "No matching values";
                this.eList.appendChild(emptyState);
                return;
            }

            visibleOptions.forEach(
                function (option) {
                    var row = document.createElement("label");
                    row.className = "laundry-set-filter-option";
                    row.title = option.label;

                    var checkbox = document.createElement("input");
                    checkbox.type = "checkbox";
                    checkbox.checked = this.selectedValues.has(option.value);
                    checkbox.addEventListener(
                        "change",
                        function (event) {
                            if (event.target.checked) {
                                this.selectedValues.add(option.value);
                            } else {
                                this.selectedValues.delete(option.value);
                            }

                            this.notifyFilterChanged();
                        }.bind(this)
                    );

                    var label = document.createElement("span");
                    label.textContent = option.label;

                    row.appendChild(checkbox);
                    row.appendChild(label);
                    this.eList.appendChild(row);
                }.bind(this)
            );
        }

        notifyFilterChanged() {
            if (this.params.filterChangedCallback) {
                this.params.filterChangedCallback();
                return;
            }

            if (this.params.api) {
                this.params.api.onFilterChanged();
            }
        }

        isFilterActive() {
            return this.selectedValues.size !== this.options.length;
        }

        doesFilterPass(filterParams) {
            var data = filterParams.data || (filterParams.node && filterParams.node.data) || {};
            return this.selectedValues.has(encodeValue(data[this.params.colDef.field]));
        }

        getModel() {
            if (!this.isFilterActive()) {
                return null;
            }

            return {
                values: allOptionValues(this.options).filter(
                    function (value) {
                        return this.selectedValues.has(value);
                    }.bind(this)
                ),
            };
        }

        setModel(model) {
            this.selectedValues = selectedSetFromModel(model, this.options);
            this.renderOptions();
        }

        getModelAsString(model) {
            return summaryFromModel(model, this.optionMap);
        }

        afterGuiAttached() {
            this.eSearchInput.focus();
            this.eSearchInput.select();
        }

        refresh(params) {
            var currentModel = this.getModel();
            this.params = params;
            this.options = getOptions(params);
            this.optionMap = buildOptionMap(this.options);
            this.selectedValues = selectedSetFromModel(currentModel, this.options);
            this.renderOptions();
            return true;
        }
    };
})();
