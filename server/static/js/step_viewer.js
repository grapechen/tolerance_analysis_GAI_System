/**
 * step_viewer.js - Three.js STEP PMI 3D 查看器模組
 * ========================================================
 * 負責處理STEP幾何三角化、PMI高亮、leader lines 渲染等
 */

const StepViewer = (() => {
    let renderer, scene, camera, controls;
    let currentSession = null;
    let container = null;        // step-viewer-container 容器 div（用於 resize 時讀實際寬高）
    let geometryMeshes   = {};   // face_id_str -> THREE.Mesh（特徵面，主色）
    let datumFaceMeshes  = {};   // row_index -> THREE.Mesh（基準參考面，綠色）※對齊 test0402 C_GREEN
    let pmiLineMeshes    = {};   // row_index -> THREE.LineSegments
    let pmiTriMeshes     = {};   // row_index -> THREE.Mesh（GDT 框/符號三角面）
    let allPmiLoaded     = false; // 是否已批次載入全部 PMI 標註（舊 Tkinter 版行為）
    let baseGeometryMesh = null;  // 整體模型基礎幾何（灰色）

    const COLORS = {
        default:     0xccddff,   // 淺藍
        datum:       0x00DA26,   // 綠色  ← C_GREEN in test0402
        interactive: 0xA121F0,   // 紫色  ← C_PURPLE in test0402
        individual:  0xFFA500,   // 橘色  ← C_ORANGE in test0402
        hover:       0xFFFF00,   // 黃色
    };

    /**
     * 初始化 Three.js 場景
     */
    function init(canvasId) {
        container = document.getElementById(canvasId);
        if (!container) {
            console.error(`❌ Canvas element not found: ${canvasId}`);
            return false;
        }

        // 建立 renderer
        renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setSize(container.clientWidth, container.clientHeight);
        renderer.setClearColor(0xfafafa);
        container.appendChild(renderer.domElement);

        // 建立 scene
        scene = new THREE.Scene();

        // 建立 camera
        const width = container.clientWidth;
        const height = container.clientHeight;
        camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 10000);
        camera.position.set(0, 0, 100);

        // 建立 OrbitControls
        controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.05;
        controls.enableZoom = true;

        // 加入基礎光源
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
        scene.add(ambientLight);

        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.5);
        directionalLight.position.set(100, 100, 100);
        scene.add(directionalLight);

        // 啟動動畫迴圈
        animate();

        // 處理視窗縮放
        window.addEventListener('resize', onWindowResize);

        console.log('✅ StepViewer 初始化完成');
        return true;
    }

    /**
     * 載入全部幾何（低精度概覽），作為半透明底模
     */
    function loadAllGeometry(sessionId, deflection = 0.3) {
        if (!sessionId) {
            console.error('❌ loadAllGeometry: 缺少 sessionId');
            return;
        }

        currentSession = sessionId;
        console.log(`⏳ 載入 session ${sessionId} 的所有幾何...`);

        fetch(`/api/step/geometry?session_id=${sessionId}&face_ids=*&deflection=${deflection}`)
            .then(r => r.json())
            .then(data => {
                if (!data.ok) {
                    console.error('❌ 幾何載入失敗:', data.error);
                    return;
                }

                if (data.geometry && data.geometry.vertices) {
                    if (baseGeometryMesh) {
                        scene.remove(baseGeometryMesh);
                    }
                    const { vertices, faces, normals } = data.geometry;
                    const geom = new THREE.BufferGeometry();
                    geom.setAttribute('position', new THREE.BufferAttribute(new Float32Array(vertices.flat()), 3));
                    if (normals && normals.length > 0) {
                        geom.setAttribute('normal', new THREE.BufferAttribute(new Float32Array(normals.flat()), 3));
                    }
                    geom.setIndex(new THREE.BufferAttribute(new Uint32Array(faces.flat()), 1));
                    geom.computeBoundingSphere();

                    const mat = new THREE.MeshStandardMaterial({
                        color: 0xcccccc,
                        transparent: true,
                        opacity: 0.3,   // 半透明底模
                        metalness: 0.1,
                        roughness: 0.8
                    });

                    baseGeometryMesh = new THREE.Mesh(geom, mat);
                    scene.add(baseGeometryMesh);

                    console.log('✅ 基礎幾何 透明底模建立完成');

                    // 等待底模讀取完後置中相機
                    focusOnGeometry();

                    // 載入所有 PMI 標註（引線 + GDT 框/符號/文字）— 對齊舊 Tkinter 版行為
                    loadAllPmiAnnotations(sessionId);
                } else {
                    console.warn('⚠️ 基礎幾何點面資料為空');
                }
            })
            .catch(err => console.error('❌ 幾何查詢錯誤:', err));
    }

    /**
     * 一次載入所有 PMI 標註到 3D 場景（引線 + GDT 框/符號/文字的三角形）
     * 對齊舊 Tkinter 版 AIS_Shape(compound) 的顯示語意。
     */
    function loadAllPmiAnnotations(sessionId) {
        if (!sessionId) return;
        if (allPmiLoaded) return;  // 避免重複載入（真正畫出東西後才算已載入）

        console.log(`⏳ 載入全部 PMI 標註 (Session: ${sessionId})...`);
        fetch('/api/step/pmi_all_geometry', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId })
        })
            .then(r => r.json())
            .then(data => {
                if (!data.ok) {
                    console.error('❌ 載入 PMI 標註失敗:', data.error);
                    return;
                }
                const items = data.items || [];
                items.forEach(item => {
                    if (item.leader_lines && item.leader_lines.length > 0) {
                        renderLeaderLines(item.leader_lines, item.row_index);
                    }
                });
                // 只有實際畫到東西才鎖定；若為 0（parse_pmi 還沒跑），允許之後再來重跑
                if (items.length > 0) {
                    allPmiLoaded = true;
                    console.log(`✅ 全部 PMI 標註載入完成：${items.length} 項`);
                } else {
                    console.log(`ℹ️ 尚無 PMI 標註（請先按 "比對 & 解析 PMI"）`);
                }
            })
            .catch(err => console.error('❌ PMI 標註載入錯誤:', err));
    }

    /**
     * 渲染 PMI 三角形（GDT 框/符號/文字）
     */
    function renderPmiTriangles(triData, rowIndex) {
        const { vertices, faces } = triData;
        if (!vertices || !faces || vertices.length === 0) return;

        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.BufferAttribute(
            new Float32Array(vertices.flat()), 3
        ));
        geometry.setIndex(new THREE.BufferAttribute(
            new Uint32Array(faces.flat()), 1
        ));
        geometry.computeVertexNormals();
        geometry.computeBoundingSphere();

        // 黑色線框 + 淡填充，對齊舊 Tkinter 版 AIS_Shape(黑色 width 1.5) 效果
        const material = new THREE.MeshBasicMaterial({
            color: 0x000000,
            wireframe: true,
            depthTest: true,
        });
        const mesh = new THREE.Mesh(geometry, material);
        scene.add(mesh);

        const key = `pmitri_${rowIndex}`;
        if (pmiTriMeshes[key]) {
            scene.remove(pmiTriMeshes[key]);
        }
        pmiTriMeshes[key] = mesh;
    }

    /**
     * 高亮指定的 PMI（拉取幾何+leader lines）
     */
    function highlightPmiRow(rowIndex) {
        if (!currentSession) {
            console.error('❌ highlightPmiRow: 沒有活躍的 session');
            return;
        }

        console.log(`🔍 高亮 PMI row ${rowIndex}...`);

        fetch(`/api/step/highlight`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentSession,
                row_index: rowIndex
            })
        })
            .then(r => r.json())
            .then(data => {
                if (!data.ok) {
                    console.error('❌ 高亮失敗:', data.error);
                    return;
                }

                // 渲染特徵面（主色：綠/紫/橘）— 對齊 test0402 _build_pmi_items Path A step 1
                if (data.face_geometry && data.face_geometry.vertices) {
                    renderFaceGeometry(data.face_geometry, data.highlight_color, rowIndex);
                }

                // 渲染基準參考面（綠色）— 對齊 test0402 _build_pmi_items Path A step 2（C_GREEN）
                if (data.datum_faces_geometry && data.datum_faces_geometry.vertices) {
                    renderDatumFaceGeometry(data.datum_faces_geometry, rowIndex);
                }

                // 渲染 leader lines（黑色）— 對齊 test0402 Path B AIS_Shape(compound) C_BLACK
                if (data.leader_lines && data.leader_lines.length > 0) {
                    renderLeaderLines(data.leader_lines, rowIndex);
                }

                console.log(`✅ PMI ${rowIndex} 高亮完成`);
                // 批次選擇時不頻繁移動視角，讓用戶自己轉動
                // focusOnGeometry();
            })
            .catch(err => console.error('❌ 高亮查詢錯誤:', err));
    }

    /**
     * 同步當下所有勾選的 PMI 項目
     */
    function syncHighlights(indices) {
        // 第一步：移除不在清單內的 meshes（特徵面、基準面、leader lines）
        Object.keys(geometryMeshes).forEach(key => {
            const idx = parseInt(key.replace('face_', ''));
            if (!indices.includes(idx)) {
                scene.remove(geometryMeshes[key]);
                if (geometryMeshes[key].geometry) geometryMeshes[key].geometry.dispose();
                if (geometryMeshes[key].material) geometryMeshes[key].material.dispose();
                delete geometryMeshes[key];
            }
        });

        Object.keys(datumFaceMeshes).forEach(key => {
            const idx = parseInt(key.replace('datum_', ''));
            if (!indices.includes(idx)) {
                scene.remove(datumFaceMeshes[key]);
                if (datumFaceMeshes[key].geometry) datumFaceMeshes[key].geometry.dispose();
                if (datumFaceMeshes[key].material) datumFaceMeshes[key].material.dispose();
                delete datumFaceMeshes[key];
            }
        });

        Object.keys(pmiLineMeshes).forEach(key => {
            const idx = parseInt(key.replace('lines_', ''));
            if (!indices.includes(idx)) {
                scene.remove(pmiLineMeshes[key]);
                if (pmiLineMeshes[key].geometry) pmiLineMeshes[key].geometry.dispose();
                if (pmiLineMeshes[key].material) pmiLineMeshes[key].material.dispose();
                delete pmiLineMeshes[key];
            }
        });

        // 第二步：新增還未載入的 highlight
        indices.forEach(idx => {
            if (!geometryMeshes[`face_${idx}`] && !datumFaceMeshes[`datum_${idx}`] && !pmiLineMeshes[`lines_${idx}`]) {
                highlightPmiRow(idx);
            }
        });
    }

    /**
     * 渲染 face 幾何
     */
    function renderFaceGeometry(geomData, colorHex, rowIndex) {
        const { vertices, faces, normals } = geomData;

        if (!vertices || !faces) {
            console.warn('⚠️ 幾何數據不完整');
            return;
        }

        // 建立 BufferGeometry
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.BufferAttribute(
            new Float32Array(vertices.flat()), 3
        ));
        if (normals && normals.length > 0) {
            geometry.setAttribute('normal', new THREE.BufferAttribute(
                new Float32Array(normals.flat()), 3
            ));
        }
        geometry.setIndex(new THREE.BufferAttribute(
            new Uint32Array(faces.flat()), 1
        ));
        geometry.computeBoundingSphere();

        // 建立材質
        const material = new THREE.MeshStandardMaterial({
            color: colorHex,
            metalness: 0.3,
            roughness: 0.7
        });

        // 建立 mesh
        const mesh = new THREE.Mesh(geometry, material);
        scene.add(mesh);

        // 快取（以便後續切換顏色或隱藏）
        const key = `face_${rowIndex}`;
        if (geometryMeshes[key]) {
            scene.remove(geometryMeshes[key]);
        }
        geometryMeshes[key] = mesh;
    }

    /**
     * 渲染基準參考面（綠色）— 對齊 test0402 C_GREEN
     * 交互公差（per/par/pos/dis...）的基準參考面獨立渲染，顏色為 COLORS.datum
     */
    function renderDatumFaceGeometry(geomData, rowIndex) {
        const { vertices, faces, normals } = geomData;
        if (!vertices || !faces) return;

        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.BufferAttribute(
            new Float32Array(vertices.flat()), 3
        ));
        if (normals && normals.length > 0) {
            geometry.setAttribute('normal', new THREE.BufferAttribute(
                new Float32Array(normals.flat()), 3
            ));
        }
        geometry.setIndex(new THREE.BufferAttribute(new Uint32Array(faces.flat()), 1));
        geometry.computeBoundingSphere();

        const material = new THREE.MeshStandardMaterial({
            color: COLORS.datum,   // 0x00DA26 綠色，對齊 test0402 C_GREEN
            metalness: 0.3,
            roughness: 0.7
        });

        const mesh = new THREE.Mesh(geometry, material);
        scene.add(mesh);

        const key = `datum_${rowIndex}`;
        if (datumFaceMeshes[key]) {
            scene.remove(datumFaceMeshes[key]);
            if (datumFaceMeshes[key].geometry) datumFaceMeshes[key].geometry.dispose();
            if (datumFaceMeshes[key].material) datumFaceMeshes[key].material.dispose();
        }
        datumFaceMeshes[key] = mesh;
    }

    /**
     * 渲染 leader lines（標註線）
     */
    function renderLeaderLines(linesData, rowIndex) {
        if (!linesData || linesData.length === 0) {
            return;
        }

        const points = [];
        linesData.forEach(line => {
            // 每條 line 是 [[x1,y1,z1], [x2,y2,z2]]
            points.push(new THREE.Vector3(...line[0]));
            points.push(new THREE.Vector3(...line[1]));
        });

        const geometry = new THREE.BufferGeometry().setFromPoints(points);
        const material = new THREE.LineBasicMaterial({ color: 0x000000, linewidth: 2 });
        const lines = new THREE.LineSegments(geometry, material);
        scene.add(lines);

        const key = `lines_${rowIndex}`;
        if (pmiLineMeshes[key]) {
            scene.remove(pmiLineMeshes[key]);
        }
        pmiLineMeshes[key] = lines;
    }

    /**
     * 清空所有高亮（保留 PMI 標註 — PMI 標註由 clearGeometry 在換 session 時清）
     */
    function clearHighlights() {
        Object.values(geometryMeshes).forEach(mesh => {
            scene.remove(mesh);
            if (mesh.geometry) mesh.geometry.dispose();
            if (mesh.material) mesh.material.dispose();
        });
        Object.values(datumFaceMeshes).forEach(mesh => {
            scene.remove(mesh);
            if (mesh.geometry) mesh.geometry.dispose();
            if (mesh.material) mesh.material.dispose();
        });
        Object.values(pmiLineMeshes).forEach(lines => {
            scene.remove(lines);
            if (lines.geometry) lines.geometry.dispose();
            if (lines.material) lines.material.dispose();
        });
        geometryMeshes  = {};
        datumFaceMeshes = {};
        pmiLineMeshes   = {};
        console.log('✅ 清空高亮');
    }

    /**
     * 設定底模（基礎幾何）透明度，0 = 完全透明，1 = 完全不透明。
     */
    function setBaseOpacity(value) {
        if (!baseGeometryMesh) return;
        const v = Math.max(0, Math.min(1, parseFloat(value)));
        baseGeometryMesh.material.opacity    = v;
        baseGeometryMesh.material.depthWrite = (v >= 0.99);
        baseGeometryMesh.material.needsUpdate = true;
    }

    /**
     * 置中並調整視角：將場景所有幾何（零件 + PMI 標註）納入視野。
     * @param {boolean} isometric - true 使用等角斜上視角，false 使用正面 Z 視角（預設 true）
     */
    function focusOnGeometry(isometric = true) {
        const boundingBox = new THREE.Box3();
        scene.traverse(obj => {
            if (obj.isMesh || obj.isLine) {
                boundingBox.expandByObject(obj);
            }
        });

        if (boundingBox.isEmpty()) {
            console.warn('⚠️ 場景為空，無法聚焦');
            return;
        }

        const center = boundingBox.getCenter(new THREE.Vector3());
        const size   = boundingBox.getSize(new THREE.Vector3());
        const maxDim = Math.max(size.x, size.y, size.z);
        const fov    = camera.fov * (Math.PI / 180);
        const dist   = (maxDim / 2 / Math.tan(fov / 2)) * 1.4;

        if (isometric) {
            // 等角斜上方：從右前上方俯視，讓零件形狀更立體易讀
            const dir = new THREE.Vector3(1, 0.7, 1).normalize();
            camera.position.copy(center).addScaledVector(dir, dist);
        } else {
            camera.position.set(center.x, center.y, center.z + dist);
        }

        camera.lookAt(center);
        controls.target.copy(center);
        controls.update();
    }

    /**
     * 釋放資源
     */
    function dispose() {
        if (renderer) {
            renderer.dispose();
        }
        scene.traverse(obj => {
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) obj.material.dispose();
        });
        window.removeEventListener('resize', onWindowResize);
        console.log('✅ StepViewer 資源已釋放');
    }

    /**
     * 窗口 / 面板縮放處理 — 讀「容器 div」的實際尺寸（不要讀 renderer.domElement，
     * 那個寬高等於最後一次 setSize 設的值，永遠跟不上 resize）。
     */
    function onWindowResize() {
        if (!container || !renderer || !camera) return;
        const width = container.clientWidth;
        const height = container.clientHeight;
        if (width === 0 || height === 0) return;  // 面板關閉時跳過
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
        renderer.setSize(width, height, false);   // false = 不去改 canvas 的 CSS 樣式
    }

    /**
     * 渲染迴圈
     */
    function animate() {
        requestAnimationFrame(animate);
        controls.update();
        renderer.render(scene, camera);
    }

    /**
     * 清除已加載的幾何（新 session 時調用）— 包含 PMI 標註
     */
    function clearGeometry() {
        if (baseGeometryMesh) {
            scene.remove(baseGeometryMesh);
            if (baseGeometryMesh.geometry) baseGeometryMesh.geometry.dispose();
            if (baseGeometryMesh.material) baseGeometryMesh.material.dispose();
            baseGeometryMesh = null;
        }
        Object.values(geometryMeshes).forEach(m => {
            scene.remove(m);
            if (m.geometry) m.geometry.dispose();
            if (m.material) m.material.dispose();
        });
        Object.values(datumFaceMeshes).forEach(m => {
            scene.remove(m);
            if (m.geometry) m.geometry.dispose();
            if (m.material) m.material.dispose();
        });
        Object.values(pmiTriMeshes).forEach(m => {
            scene.remove(m);
            if (m.geometry) m.geometry.dispose();
            if (m.material) m.material.dispose();
        });
        Object.values(pmiLineMeshes).forEach(m => {
            scene.remove(m);
            if (m.geometry) m.geometry.dispose();
            if (m.material) m.material.dispose();
        });
        geometryMeshes  = {};
        datumFaceMeshes = {};
        pmiTriMeshes    = {};
        pmiLineMeshes   = {};
        allPmiLoaded    = false;
        currentSession  = null;
    }

    // 暴露公共 API
    return {
        init,
        loadAllGeometry,
        loadAllPmiAnnotations,
        clearGeometry,
        highlightPmiRow,
        syncHighlights,
        clearHighlights,
        focusOnGeometry,
        setBaseOpacity,
        onResize: onWindowResize,
        dispose
    };
})();
