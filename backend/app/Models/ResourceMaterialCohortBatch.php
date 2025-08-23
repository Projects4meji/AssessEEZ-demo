<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class ResourceMaterialCohortBatch extends Model
{
    use HasFactory, SoftDeletes;

    protected $fillable = [
        'id',
        'resource_material_id',
        'cohort_batch_no',
        'status',
        'created_by',
        'updated_by',
        'created_at',
        'updated_at',
        'deleted_at'
    ];
}
