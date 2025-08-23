<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class QualificationUnit extends Model
{
    use HasFactory, SoftDeletes;

    protected $fillable = [
        'id',
        'qualification_id',
        'unit_number',
        'unit_title',
        'unit_type_id',
        'status',
        'created_by',
        'updated_by',
        'created_at',
        'updated_at',
        'deleted_at'
    ];
}
