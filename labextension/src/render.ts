import * as SmilesDrawerImport from 'smiles-drawer';
import * as molstar from 'molstar/build/viewer/molstar';

const SmilesDrawerLib: any = (SmilesDrawerImport as any).default ?? SmilesDrawerImport;

function initSmiles(root: HTMLElement): void {
  const elements = Array.from(
    root.querySelectorAll<HTMLElement>('[data-refua-smiles="1"]')
  );

  elements.forEach((element) => {
    if (element.dataset.refuaRendered === 'true') {
      return;
    }

    const smiles = element.getAttribute('data-smiles');
    if (!smiles) {
      return;
    }

    const theme = element.getAttribute('data-theme') || 'light';
    const explicitHydrogens =
      element.getAttribute('data-explicit-hydrogens') === 'true';
    const width = parseInt(
      element.getAttribute('data-width') || element.getAttribute('width') || '400',
      10
    );
    const height = parseInt(
      element.getAttribute('data-height') || element.getAttribute('height') || '300',
      10
    );

    const options = {
      width,
      height,
      padding: 12,
      explicitHydrogens,
      compactDrawing: false
    };

    const errorEl =
      element.id && root.ownerDocument
        ? root.ownerDocument.getElementById(`${element.id}-error`)
        : null;

    try {
      SmilesDrawerLib.parse(
        smiles,
        (tree: any) => {
          try {
            const DrawerClass =
              element.tagName.toLowerCase() === 'svg'
                ? SmilesDrawerLib.SvgDrawer
                : SmilesDrawerLib.Drawer;
            const drawer = new DrawerClass(options);
            drawer.draw(tree, element, theme);
            element.dataset.refuaRendered = 'true';
          } catch (drawErr: any) {
            console.error('Failed to draw SMILES:', drawErr);
            if (errorEl) {
              errorEl.textContent = 'Failed to render structure';
              (errorEl as HTMLElement).style.display = 'block';
            }
          }
        },
        (parseErr: any) => {
          console.error('Failed to parse SMILES:', parseErr);
          if (errorEl) {
            errorEl.textContent = `Invalid SMILES: ${parseErr}`;
            (errorEl as HTMLElement).style.display = 'block';
          }
        }
      );
    } catch (err: any) {
      console.error('SmilesDrawer error:', err);
      if (errorEl) {
        errorEl.textContent = 'Error rendering structure';
        (errorEl as HTMLElement).style.display = 'block';
      }
    }
  });
}

function initMolstar(root: HTMLElement): void {
  const containers = Array.from(
    root.querySelectorAll<HTMLElement>('[data-refua-molstar="1"]')
  );

  containers.forEach((container) => {
    if (
      container.dataset.refuaRendered === 'true' ||
      container.dataset.refuaRendering === 'true'
    ) {
      return;
    }

    const url = container.getAttribute('data-url');
    const format = container.getAttribute('data-format') || 'mmcif';
    const ligandName = container.getAttribute('data-ligand') || '';
    const colorPlanRaw = container.getAttribute('data-color-plan') || '';
    let colorPlan: Record<string, unknown> = {};
    if (colorPlanRaw) {
      try {
        const parsed = JSON.parse(colorPlanRaw);
        if (parsed && typeof parsed === 'object') {
          colorPlan = parsed as Record<string, unknown>;
        }
      } catch {
        colorPlan = {};
      }
    }
    const showControls = container.getAttribute('data-controls') === 'true';
    const isInlineDataUrl = typeof url === 'string' && url.trim().startsWith('data:');

    const viewerEl = container.querySelector<HTMLElement>(
      '[data-refua-molstar-viewer="1"]'
    );
    const loadingEl = container.querySelector<HTMLElement>(
      '[data-refua-molstar-loading="1"]'
    );

    if (!url || !viewerEl) {
      if (loadingEl) {
        loadingEl.textContent = 'No structure data';
      }
      return;
    }

    const initializeViewer = (attempt = 0): void => {
      if (!viewerEl.isConnected) {
        if (attempt >= 20) {
          delete container.dataset.refuaRendering;
          if (loadingEl) {
            loadingEl.textContent = 'Failed to create viewer';
            loadingEl.style.display = 'block';
          }
          return;
        }
        requestAnimationFrame(() => initializeViewer(attempt + 1));
        return;
      }

      try {
        const looksLikeTextCifDataUrl = (candidateUrl: string): boolean => {
          if (!candidateUrl.startsWith('data:')) {
            return false;
          }
          const commaIndex = candidateUrl.indexOf(',');
          if (commaIndex < 0) {
            return false;
          }

          const meta = candidateUrl.slice(5, commaIndex).toLowerCase();
          const payload = candidateUrl.slice(commaIndex + 1);
          try {
            let sample = '';
            if (meta.includes(';base64')) {
              const compact = payload.replace(/\s+/g, '');
              const chunk = compact.slice(0, 4096);
              const padded = chunk + '='.repeat((4 - (chunk.length % 4)) % 4);
              sample = atob(padded).slice(0, 512);
            } else {
              sample = decodeURIComponent(payload.slice(0, 512));
            }

            const trimmed = sample.replace(/^\s+/, '');
            if (!trimmed) {
              return false;
            }
            return (
              trimmed.startsWith('data_') ||
              trimmed.startsWith('loop_') ||
              trimmed.startsWith('_')
            );
          } catch {
            return false;
          }
        };

        const normalizeChainGroups = (rawGroups: unknown): string[][] => {
          if (!Array.isArray(rawGroups)) {
            return [];
          }
          const seen = new Set<string>();
          const groups: string[][] = [];
          for (const rawGroup of rawGroups) {
            if (!Array.isArray(rawGroup)) {
              continue;
            }
            const chainIds: string[] = [];
            for (const rawToken of rawGroup) {
              const token = String(rawToken ?? '').trim();
              if (!token || seen.has(token)) {
                continue;
              }
              seen.add(token);
              chainIds.push(token);
            }
            if (chainIds.length > 0) {
              groups.push(chainIds);
            }
          }
          return groups;
        };

        const makeChainSelector = (
          chainIds: string[]
        ): Record<string, string> | Array<Record<string, string>> | null => {
          if (!Array.isArray(chainIds) || chainIds.length === 0) {
            return null;
          }
          const selectors: Array<Record<string, string>> = [];
          const seen = new Set<string>();
          for (const rawToken of chainIds) {
            const token = String(rawToken ?? '').trim();
            if (!token) {
              continue;
            }
            const labelKey = `label:${token}`;
            if (!seen.has(labelKey)) {
              seen.add(labelKey);
              selectors.push({ label_asym_id: token });
            }
            const authKey = `auth:${token}`;
            if (!seen.has(authKey)) {
              seen.add(authKey);
              selectors.push({ auth_asym_id: token });
            }
          }
          if (selectors.length === 0) {
            return null;
          }
          return selectors.length === 1 ? selectors[0] : selectors;
        };

        const addChainRepresentation = (
          structure: any,
          chainIds: string[],
          type: string,
          color: string,
          opacity = 1
        ): any => {
          const selector = makeChainSelector(chainIds);
          if (!selector) {
            return null;
          }
          const component = structure.component({ selector });
          component.representation({ type }).color({ color, opacity });
          return component;
        };

        const applyColorPlan = (structure: any): void => {
          const proteinPalette = [
            '#2563eb',
            '#0891b2',
            '#7c3aed',
            '#0f766e',
            '#059669',
            '#f59e0b',
            '#dc2626',
            '#9333ea'
          ];
          const ligandPalette = ['#db2777', '#c026d3', '#e11d48', '#be185d', '#ec4899'];
          const proteinGroups = normalizeChainGroups(colorPlan?.protein_chain_groups);
          const nucleicGroups = normalizeChainGroups(colorPlan?.nucleic_chain_groups);
          const ligandGroups = normalizeChainGroups(colorPlan?.ligand_chain_groups);
          const ionGroups = normalizeChainGroups(colorPlan?.ion_chain_groups);
          const otherGroups = normalizeChainGroups(colorPlan?.other_chain_groups);

          if (proteinGroups.length > 0) {
            proteinGroups.forEach((chainIds, idx) => {
              addChainRepresentation(
                structure,
                chainIds,
                'cartoon',
                proteinPalette[idx % proteinPalette.length],
                1
              );
            });
          } else {
            structure
              .component({ selector: 'protein' })
              .representation({ type: 'cartoon' })
              .color({ color: '#2563eb' });
          }

          if (nucleicGroups.length > 0) {
            nucleicGroups.forEach((chainIds) => {
              addChainRepresentation(structure, chainIds, 'cartoon', '#f59e0b', 1);
            });
          } else {
            structure
              .component({ selector: 'nucleic' })
              .representation({ type: 'cartoon' })
              .color({ color: '#f59e0b' });
          }

          if (ligandGroups.length > 0) {
            ligandGroups.forEach((chainIds, idx) => {
              const ligandComp = addChainRepresentation(
                structure,
                chainIds,
                'ball_and_stick',
                ligandPalette[idx % ligandPalette.length],
                1
              );
              if (ligandName && idx === 0 && ligandComp) {
                ligandComp.label({ text: ligandName });
              }
            });
          } else {
            const ligandComp = structure.component({ selector: 'ligand' });
            if (ligandName) {
              ligandComp.label({ text: ligandName });
            }
            ligandComp
              .representation({ type: 'ball_and_stick' })
              .color({ color: '#db2777' });
          }

          if (ionGroups.length > 0) {
            ionGroups.forEach((chainIds) => {
              addChainRepresentation(structure, chainIds, 'ball_and_stick', '#14b8a6', 1);
            });
          } else {
            structure
              .component({ selector: 'ion' })
              .representation({ type: 'ball_and_stick' })
              .color({ color: '#14b8a6' });
          }

          structure
            .component({ selector: 'branched' })
            .representation({ type: 'ball_and_stick' })
            .color({ color: '#84cc16' });

          otherGroups.forEach((chainIds) => {
            addChainRepresentation(structure, chainIds, 'ball_and_stick', '#64748b', 1);
          });
        };

        const loadWithMvs = async (viewer: any): Promise<boolean> => {
          const mvs = (molstar as any)?.PluginExtensions?.mvs;
          if (!mvs?.MVSData || typeof mvs.loadMVS !== 'function') {
            return false;
          }

          try {
            let normalizedFormat = (format || 'mmcif').toLowerCase();
            if (
              normalizedFormat === 'bcif' &&
              isInlineDataUrl &&
              looksLikeTextCifDataUrl(url)
            ) {
              normalizedFormat = 'mmcif';
            }
            const builder = mvs.MVSData.createBuilder();
            const structure = builder
              .download({ url })
              .parse({ format: normalizedFormat })
              .modelStructure({});
            applyColorPlan(structure);

            const mvsState = builder.getState();
            await mvs.loadMVS(viewer.plugin, mvsState, {
              sourceUrl: null,
              sanityChecks: true,
              replaceExisting: false
            });
            container.dataset.refuaLoadedFormat = normalizedFormat;
            return true;
          } catch (err: any) {
            console.warn('MVS load failed; falling back to direct structure load.', err);
            return false;
          }
        };

        const loadDirectly = async (viewer: any): Promise<void> => {
          if (typeof viewer.loadStructureFromUrl !== 'function') {
            throw new Error('Mol* viewer does not support loadStructureFromUrl');
          }
          let normalizedFormat = (format || 'mmcif').toLowerCase();
          let isBinary = normalizedFormat === 'bcif';
          const directLoadOptions = {
            representationParams: {
              theme: { globalName: 'entity-id' }
            }
          };
          if (
            normalizedFormat === 'bcif' &&
            isInlineDataUrl &&
            looksLikeTextCifDataUrl(url)
          ) {
            normalizedFormat = 'mmcif';
            isBinary = false;
          }
          await viewer.loadStructureFromUrl(
            url,
            normalizedFormat,
            isBinary,
            directLoadOptions
          );
          container.dataset.refuaLoadedFormat = normalizedFormat;
          container.dataset.refuaLoadedPath = 'direct';
        };

        // Pass the actual element to avoid document-level id lookups during
        // notebook restoration before output nodes are fully attached.
        molstar.Viewer.create(viewerEl, {
          layoutIsExpanded: false,
          layoutShowControls: showControls,
          layoutShowRemoteState: false,
          layoutShowSequence: true,
          layoutShowLog: false,
          layoutShowLeftPanel: showControls,
          viewportShowExpand: showControls,
          viewportShowSelectionMode: false,
          viewportShowAnimation: showControls,
          viewportShowTrajectoryControls: showControls,
          disabledExtensions: ['volumes-and-segmentations']
        })
          .then(async (viewer: any) => {
            const loadedWithMvs = await loadWithMvs(viewer);
            if (!loadedWithMvs) {
              await loadDirectly(viewer);
            } else {
              container.dataset.refuaLoadedPath = 'mvs';
            }

            if (loadingEl) {
              loadingEl.style.display = 'none';
            }
            viewer.plugin.managers.camera.reset();
            container.dataset.refuaRendered = 'true';
            delete container.dataset.refuaRendering;
          })
          .catch((err: any) => {
            console.error('Failed to load structure viewer:', err);
            delete container.dataset.refuaRendering;
            if (loadingEl) {
              loadingEl.textContent = 'Failed to load structure';
              loadingEl.style.display = 'block';
            }
          });
      } catch (err: any) {
        console.error('Mol* render error:', err);
        delete container.dataset.refuaRendering;
        if (loadingEl) {
          loadingEl.textContent = 'Failed to render structure';
        }
      }
    };

    container.dataset.refuaRendering = 'true';
    initializeViewer();
  });
}

function initComplexTabs(root: HTMLElement): void {
  const complexes = Array.from(
    root.querySelectorAll<HTMLElement>('.complex-view[data-refua-widget="complex"]')
  );

  complexes.forEach((complexRoot) => {
    if (complexRoot.dataset.refuaTabsInit === 'true') {
      return;
    }

    const buttons = Array.from(
      complexRoot.querySelectorAll<HTMLElement>('[data-complex-tab]')
    );
    const panels = Array.from(
      complexRoot.querySelectorAll<HTMLElement>('[data-complex-panel]')
    );

    const activate = (tabId: string | null) => {
      if (!tabId) {
        return;
      }
      buttons.forEach((btn) => {
        const active = btn.getAttribute('data-complex-tab') === tabId;
        btn.classList.toggle('active', active);
        btn.setAttribute('aria-selected', active ? 'true' : 'false');
      });
      panels.forEach((panel) => {
        const active = panel.getAttribute('data-complex-panel') === tabId;
        panel.classList.toggle('active', active);
      });
    };

    if (buttons.length) {
      buttons.forEach((btn) => {
        btn.addEventListener('click', () =>
          activate(btn.getAttribute('data-complex-tab'))
        );
      });
      activate(buttons[0].getAttribute('data-complex-tab'));
    } else if (panels.length) {
      panels[0].classList.add('active');
    }

    complexRoot.dataset.refuaTabsInit = 'true';
  });
}

function initAdmetViews(root: HTMLElement): void {
  const admetViews = Array.from(
    root.querySelectorAll<HTMLElement>('.admet-view[data-refua-widget="admet"]')
  );

  admetViews.forEach((admetRoot) => {
    if (admetRoot.dataset.refuaAdmetInit === 'true') {
      return;
    }

    const tabs = Array.from(
      admetRoot.querySelectorAll<HTMLElement>('[data-admet-tab]')
    );
    const panels = Array.from(
      admetRoot.querySelectorAll<HTMLElement>('[data-admet-panel]')
    );
    const rows = Array.from(
      admetRoot.querySelectorAll<HTMLElement>('[data-admet-row="1"]')
    );
    const filterInput = admetRoot.querySelector<HTMLInputElement>(
      'input[data-admet-filter="1"]'
    );

    const applyFilter = () => {
      const query = (filterInput?.value || '').trim().toLowerCase();

      rows.forEach((row) => {
        const searchText = (row.getAttribute('data-admet-search') || '').toLowerCase();
        const visible = !query || searchText.includes(query);
        row.style.display = visible ? 'flex' : 'none';
      });

      panels.forEach((panel) => {
        const panelRows = Array.from(
          panel.querySelectorAll<HTMLElement>('[data-admet-row="1"]')
        );
        const hasVisibleRows = panelRows.some((row) => row.style.display !== 'none');
        const emptyState = panel.querySelector<HTMLElement>('[data-admet-empty="1"]');
        if (emptyState) {
          emptyState.style.display = hasVisibleRows ? 'none' : 'block';
        }

        const sections = Array.from(panel.querySelectorAll<HTMLElement>('.admet-section'));
        sections.forEach((section) => {
          const sectionRows = Array.from(
            section.querySelectorAll<HTMLElement>('[data-admet-row="1"]')
          );
          const hasVisibleSectionRows = sectionRows.some(
            (row) => row.style.display !== 'none'
          );
          section.style.display = hasVisibleSectionRows ? 'block' : 'none';
        });
      });
    };

    const activate = (tabId: string | null) => {
      if (!tabId) {
        return;
      }

      tabs.forEach((tab) => {
        const active = tab.getAttribute('data-admet-tab') === tabId;
        tab.classList.toggle('active', active);
        tab.setAttribute('aria-selected', active ? 'true' : 'false');
      });

      panels.forEach((panel) => {
        const active = panel.getAttribute('data-admet-panel') === tabId;
        panel.classList.toggle('active', active);
      });

      applyFilter();
    };

    tabs.forEach((tab) => {
      tab.addEventListener('click', () =>
        activate(tab.getAttribute('data-admet-tab'))
      );
    });

    if (tabs.length) {
      activate(tabs[0].getAttribute('data-admet-tab'));
    } else if (panels.length) {
      panels[0].classList.add('active');
    }

    if (filterInput) {
      filterInput.addEventListener('input', applyFilter);
    }

    applyFilter();
    admetRoot.dataset.refuaAdmetInit = 'true';
  });
}

export function initRefuaWidgets(root: HTMLElement): void {
  initComplexTabs(root);
  initAdmetViews(root);
  initSmiles(root);
  initMolstar(root);
}
