// Tick logic of the selective-sync dialog (picker.qml): pure functions, no QML
// objects, so tests can run them with node (tests/test_protocol.py).
//
// Model. Nodes come depth-first: {rel, depth, synced, parent, loose?}.
// own[rel] is the folder's own tick; a folder is effectively on only if its
// own tick and those of all ancestors are on. Derived state of a folder:
//   "off"      not effectively on (excluded)
//   "partial"  effectively on, but some listed descendant is off
//   "on"       effectively on, every listed descendant on
// auto[rel] marks a folder that was opened as "partial" only because a
// descendant under it was ticked (see toggle).
//
// Rules (keep them simple and predictable):
//  - Click on "on": the folder goes off (descendant ticks are remembered).
//  - Click on "partial": the folder and every descendant go on (fully synced).
//  - Click on "off": if it was synced at the start and no ancestor is off, its
//    previous ticks come back; otherwise it is ticked together with every
//    descendant. Every off ancestor becomes "partial": it is ticked, its other
//    subfolders stay off, and it is marked auto.
//  - Unticking leaves an auto folder with no on subfolder: it reverts to off
//    (and so on up the chain, while the parent is auto too).

function buildIndex(nodes) {
    var parent = {}, kids = {}, order = [], byRel = {}
    for (var i = 0; i < nodes.length; ++i) {
        var n = nodes[i]
        var p = (n.parent === undefined || n.parent === null) ? null : n.parent
        parent[n.rel] = p
        byRel[n.rel] = n
        order.push(n.rel)
        if (!(p in kids) && p !== null) kids[p] = []
        if (p !== null) kids[p].push(n.rel)
    }
    return { parent: parent, kids: kids, order: order, byRel: byRel }
}

function initialOwn(nodes) {
    var own = {}
    for (var i = 0; i < nodes.length; ++i) own[nodes[i].rel] = nodes[i].synced === true
    return own
}

// {eff, state} maps for every node, in O(n).
function compute(ix, own) {
    var eff = {}, anyOff = {}, state = {}
    var i, rel, p
    for (i = 0; i < ix.order.length; ++i) {
        rel = ix.order[i]
        p = ix.parent[rel]
        eff[rel] = own[rel] === true && (p === null || eff[p] === true)
    }
    for (i = ix.order.length - 1; i >= 0; --i) {
        rel = ix.order[i]
        var list = ix.kids[rel] || []
        var off = false
        for (var k = 0; k < list.length && !off; ++k)
            off = !eff[list[k]] || anyOff[list[k]] === true
        anyOff[rel] = off
        state[rel] = !eff[rel] ? "off" : (off ? "partial" : "on")
    }
    return { eff: eff, state: state }
}

function descendants(ix, rel) {
    var out = [], stack = (ix.kids[rel] || []).slice()
    while (stack.length > 0) {
        var r = stack.pop()
        out.push(r)
        var list = ix.kids[r] || []
        for (var i = 0; i < list.length; ++i) stack.push(list[i])
    }
    return out
}

// Ancestors from the top down.
function ancestors(ix, rel) {
    var out = [], p = ix.parent[rel]
    while (p !== null && p !== undefined) { out.unshift(p); p = ix.parent[p] }
    return out
}

function setSubtree(ix, own, auto, rel) {
    own[rel] = true
    delete auto[rel]
    var d = descendants(ix, rel)
    for (var i = 0; i < d.length; ++i) { own[d[i]] = true; delete auto[d[i]] }
}

// Click on `rel`. Returns {own, auto} (new objects).
function toggle(ix, ownIn, autoIn, rel) {
    var own = Object.assign({}, ownIn), auto = Object.assign({}, autoIn)
    var st = compute(ix, own).state[rel]
    if (st === "partial") {
        setSubtree(ix, own, auto, rel)
    } else if (st === "on") {
        own[rel] = false
        delete auto[rel]
        var up = ancestors(ix, rel).reverse()
        for (var i = 0; i < up.length; ++i) {
            var a = up[i]
            if (auto[a] !== true) break
            var c = compute(ix, own).eff
            var list = ix.kids[a] || []
            var anyOn = false
            for (var k = 0; k < list.length && !anyOn; ++k) anyOn = c[list[k]] === true
            if (anyOn) break
            own[a] = false
            delete auto[a]
        }
    } else {
        var anc = ancestors(ix, rel)
        var closed = anc.filter(function (a) { return own[a] !== true })
        if (closed.length === 0 && ix.byRel[rel].synced === true) {
            own[rel] = true
        } else {
            var onPath = {}
            anc.forEach(function (a) { onPath[a] = true })
            onPath[rel] = true
            closed.forEach(function (a) {
                own[a] = true
                auto[a] = true
                var list = ix.kids[a] || []
                for (var k = 0; k < list.length; ++k)
                    if (!onPath[list[k]]) own[list[k]] = false
            })
            setSubtree(ix, own, auto, rel)
        }
    }
    return { own: own, auto: auto }
}

// What Apply would do: effective changes against the initial state, the
// counts for the status line and the loose-file warnings.
function plan(ix, nodes, own, auto) {
    var now = compute(ix, own)
    var before = compute(ix, initialOwn(nodes))
    var excl = [], incl = [], inclSet = {}, explicit = {}, partial = [], opened = [], warn = []
    for (var i = 0; i < nodes.length; ++i) {
        var rel = nodes[i].rel
        var was = before.eff[rel], is = now.eff[rel]
        if (was && !is) excl.push(rel)
        if (!was && is) {
            incl.push(rel)
            inclSet[rel] = true
            if (auto[rel] !== true) explicit[rel] = true
            var isPartial = now.state[rel] === "partial"
            if (isPartial) partial.push(rel)
            // Synced as a side effect (opened by a tick below it) or with some
            // subfolders excluded: its loose files come along, so warn.
            if (isPartial || auto[rel] === true) {
                opened.push(rel)
                var loose = nodes[i].loose
                if (loose && loose.count > 0)
                    warn.push({ rel: rel, count: loose.count, bytes: loose.bytes, files: loose.files })
            }
        }
    }
    var exclSet = {}
    excl.forEach(function (r) { exclSet[r] = true })
    var exclTop = excl.filter(function (r) { return !exclSet[ix.parent[r]] }).length
    var inclTop = Object.keys(explicit).filter(function (r) {
        var p = ix.parent[r]
        while (p !== null && p !== undefined) {
            if (explicit[p]) return false
            p = ix.parent[p]
        }
        return true
    }).length
    return { excl: excl, incl: incl, exclTop: exclTop, inclTop: inclTop,
             partial: partial, opened: opened, warn: warn, state: now.state, eff: now.eff }
}

if (typeof module !== "undefined") {
    module.exports = { buildIndex: buildIndex, initialOwn: initialOwn, compute: compute,
                       toggle: toggle, plan: plan }
}
